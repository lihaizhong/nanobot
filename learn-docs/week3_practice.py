"""
Week 3 实践练习：消息处理流程演示

这个文件演示 MessageBus 和 SessionManager 如何协同工作，
处理一条完整的用户消息。

运行方式：
    python -m learn-docs.week3_practice
"""

import asyncio
from datetime import datetime
from dataclasses import dataclass, field
from typing import Callable, Any, Optional, List, Dict, Awaitable
from pathlib import Path
import json
import tempfile

# ============================================================
# Part 1: 消息类型定义 (简化版，实际代码在 nanobot/bus/events.py)
# ============================================================

@dataclass
class InboundMessage:
    """入站消息：用户发送给 bot 的消息"""
    channel: str                    # 消息来源通道 (telegram, discord 等)
    sender_id: str                  # 发送者 ID
    chat_id: str                    # 会话 ID
    content: str                    # 消息内容
    timestamp: datetime = field(default_factory=datetime.now)
    session_key_override: Optional[str] = None  # 可选的 session key 覆盖


@dataclass
class OutboundMessage:
    """出站消息：bot 发送给用户的响应"""
    channel: str                    # 目标通道
    chat_id: str                    # 目标会话 ID
    content: str                    # 响应内容
    reply_to: Optional[str] = None     # 回复的消息 ID
    media: Optional[List[Any]] = None       # 附件媒体
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# Part 2: MessageBus 实现 (简化版，实际代码在 nanobot/bus/queue.py)
# ============================================================

class MessageBus:
    """
    消息总线：使用 asyncio.Queue 实现生产者-消费者模式
    
    关键点：
    - 使用 asyncio.Queue 进行异步消息传递
    - 分离入站和出站消息队列
    - 支持多个消费者并发处理
    """
    
    def __init__(self):
        self._inbound_queue: "asyncio.Queue[InboundMessage]" = asyncio.Queue()
        self._outbound_queue: "asyncio.Queue[OutboundMessage]" = asyncio.Queue()
        self._outbound_handlers: List[Callable[[OutboundMessage], Awaitable[Any]]] = []
    
    async def publish_inbound(self, message: InboundMessage) -> None:
        """发布入站消息到队列"""
        print(f"[MessageBus] 📥 收到入站消息: {message.content[:50]}...")
        await self._inbound_queue.put(message)
    
    async def consume_inbound(self) -> InboundMessage:
        """消费入站消息（阻塞等待）"""
        return await self._inbound_queue.get()
    
    async def publish_outbound(self, message: OutboundMessage) -> None:
        """发布出站消息，通知所有处理器"""
        print(f"[MessageBus] 📤 发送出站消息: {message.content[:50]}...")
        await self._outbound_queue.put(message)
        # 通知所有注册的处理器
        for handler in self._outbound_handlers:
            await handler(message)
    
    def register_outbound_handler(self, handler: Callable[[OutboundMessage], Any]) -> None:
        """注册出站消息处理器"""
        self._outbound_handlers.append(handler)


# ============================================================
# Part 3: Session 实现 (简化版，实际代码在 nanobot/session/manager.py)
# ============================================================

@dataclass
class Session:
    """会话：存储单个对话的所有状态"""
    key: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_consolidated: int = 0  # 已整合到长期记忆的消息数量


class SessionManager:
    """
    会话管理器：负责会话的创建、加载、保存
    
    关键点：
    - 使用内存缓存 (_cache) 加速频繁访问的会话
    - 使用 JSONL 文件持久化会话数据
    - Session Key = channel:chat_id 实现会话隔离
    """
    
    def __init__(self, sessions_dir: Path):
        self._sessions_dir = sessions_dir
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Session] = {}
    
    def get_or_create(self, key: str) -> Session:
        """获取或创建会话（懒加载）"""
        # 1. 先查内存缓存
        if key in self._cache:
            print(f"[SessionManager] 📦 从缓存获取会话: {key}")
            return self._cache[key]
        
        # 2. 从磁盘加载
        session = self._load(key)
        if session is None:
            # 3. 都没有则创建新的
            print(f"[SessionManager] ✨ 创建新会话: {key}")
            session = Session(key=key)
        else:
            print(f"[SessionManager] 💾 从磁盘加载会话: {key}")
        
        # 4. 放入缓存
        self._cache[key] = session
        return session
    
    def _load(self, key: str) -> Optional[Session]:
        """从磁盘加载会话"""
        path = self._sessions_dir / f"{key}.jsonl"
        if not path.exists():
            return None
        
        messages = []
        metadata = {}
        created_at = None
        last_consolidated = 0
        
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if data.get("_type") == "metadata":
                    metadata = data.get("metadata", {})
                    created_at = datetime.fromisoformat(data["created_at"])
                    last_consolidated = data.get("last_consolidated", 0)
                else:
                    messages.append(data)
        
        return Session(
            key=key,
            messages=messages,
            created_at=created_at or datetime.now(),
            metadata=metadata,
            last_consolidated=last_consolidated
        )
    
    def save(self, session: Session) -> None:
        """保存会话到磁盘"""
        session.updated_at = datetime.now()
        path = self._sessions_dir / f"{session.key}.jsonl"
        
        with open(path, "w", encoding="utf-8") as f:
            # 写入元数据行
            metadata_line = {
                "_type": "metadata",
                "key": session.key,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "metadata": session.metadata,
                "last_consolidated": session.last_consolidated
            }
            f.write(json.dumps(metadata_line, ensure_ascii=False) + "\n")
            # 写入消息
            for msg in session.messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
        
        print(f"[SessionManager] 💾 会话已保存: {session.key}")
    
    def add_message(self, session: Session, role: str, content: str) -> None:
        """向会话添加消息"""
        session.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })


# ============================================================
# Part 4: 消息处理器 - 演示完整流程
# ============================================================

class MessageHandler:
    """
    消息处理器：演示 MessageBus 和 SessionManager 的协作
    
    流程：
    1. 从 MessageBus 获取入站消息
    2. 根据 channel:chat_id 获取/创建 Session
    3. 将用户消息添加到 Session
    4. 生成响应（这里用简单的 echo 演示）
    5. 将响应添加到 Session
    6. 保存 Session
    7. 通过 MessageBus 发送出站消息
    """
    
    def __init__(self, bus: MessageBus, session_manager: SessionManager):
        self.bus = bus
        self.session_manager = session_manager
    
    async def process_message(self, inbound: InboundMessage) -> OutboundMessage:
        """处理单条消息的完整流程"""
        
        # 1. 生成 Session Key
        session_key = f"{inbound.channel}:{inbound.chat_id}"
        if inbound.session_key_override:
            session_key = inbound.session_key_override
        
        print(f"\n{'='*60}")
        print(f"[Handler] 开始处理消息，Session Key: {session_key}")
        
        # 2. 获取或创建会话
        session = self.session_manager.get_or_create(session_key)
        
        # 3. 添加用户消息到会话
        self.session_manager.add_message(session, "user", inbound.content)
        print(f"[Handler] 用户消息已添加，当前消息数: {len(session.messages)}")
        
        # 4. 生成响应（这里用简单的 echo，实际会调用 LLM）
        response_content = self._generate_response(session, inbound.content)
        
        # 5. 添加助手响应到会话
        self.session_manager.add_message(session, "assistant", response_content)
        
        # 6. 保存会话
        self.session_manager.save(session)
        
        # 7. 创建并发送出站消息
        outbound = OutboundMessage(
            channel=inbound.channel,
            chat_id=inbound.chat_id,
            content=response_content
        )
        
        print(f"[Handler] 消息处理完成")
        print(f"{'='*60}\n")
        
        return outbound
    
    def _generate_response(self, session: Session, user_input: str) -> str:
        """生成响应（简化版，实际会调用 LLM）"""
        # 简单的 echo 响应，演示用
        msg_count = len(session.messages)
        return f"Echo (消息 #{msg_count}): {user_input}"


# ============================================================
# Part 5: 运行演示
# ============================================================

async def demo():
    """运行完整的消息处理演示"""
    
    print("=" * 60)
    print("🚀 Week 3 实践演示：消息处理流程")
    print("=" * 60)
    
    # 创建临时目录存储会话
    with tempfile.TemporaryDirectory() as tmpdir:
        sessions_dir = Path(tmpdir) / "sessions"
        
        # 初始化组件
        bus = MessageBus()
        session_manager = SessionManager(sessions_dir)
        handler = MessageHandler(bus, session_manager)
        
        # 注册出站消息处理器（模拟发送到通道）
        async def send_to_channel(message: OutboundMessage):
            print(f"[Channel] 📱 发送到 {message.channel}/{message.chat_id}: {message.content}")
        
        bus.register_outbound_handler(send_to_channel)
        
        # 模拟用户消息
        messages = [
            InboundMessage(
                channel="telegram",
                sender_id="user_123",
                chat_id="chat_456",
                content="你好，这是第一条消息！"
            ),
            InboundMessage(
                channel="telegram",
                sender_id="user_123",
                chat_id="chat_456",
                content="这是第二条消息，会话应该被保持。"
            ),
            InboundMessage(
                channel="discord",
                sender_id="user_789",
                chat_id="channel_abc",
                content="来自 Discord 的消息，这是不同的会话。"
            ),
        ]
        
        # 处理每条消息
        for i, msg in enumerate(messages, 1):
            print(f"\n📨 处理第 {i} 条消息...")
            outbound = await handler.process_message(msg)
            await bus.publish_outbound(outbound)
        
        # 显示最终会话状态
        print("\n" + "=" * 60)
        print("📊 最终会话状态:")
        print("=" * 60)
        
        for key, session in session_manager._cache.items():
            print(f"\n会话: {key}")
            print(f"  消息数: {len(session.messages)}")
            print(f"  创建时间: {session.created_at}")
            print(f"  更新时间: {session.updated_at}")


if __name__ == "__main__":
    asyncio.run(demo())