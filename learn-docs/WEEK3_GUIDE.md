# 第 3 周学习指南：消息总线和会话管理

## 🎯 本周目标

掌握 nanobot 的消息处理核心，学会：
1. **理解** 消息总线 (MessageBus) 的工作原理
2. **分析** InboundMessage 和 OutboundMessage 的生命周期
3. **掌握** Session 隔离和持久化机制
4. **实现** 一个自定义消息处理器

---

## 🏗️ 核心架构

```
用户消息 → 通道 (Channel) → InboundMessage
    ↓
MessageBus.publish_inbound() → 队列存储
    ↓
AgentLoop 处理 → LLM 调用 → 工具执行
    ↓
OutboundMessage → MessageBus.publish_outbound()
    ↓
通道发送响应 → 用户
```

---

## 📖 Part 1: 消息总线 (MessageBus)

### 代码位置

[nanobot/bus/](nanobot/bus/)

```
nanobot/bus/
├── __init__.py
├── events.py      # InboundMessage, OutboundMessage 定义
├── queue.py       # MessageBus 实现
```

### MessageBus 核心方法

```python
class MessageBus:
    async def publish_inbound(self, message: InboundMessage) -> None:
        """发布入站消息到队列"""
        pass
    
    async def publish_outbound(self, message: OutboundMessage) -> None:
        """发布出站消息"""
        pass
    
    async def subscribe_inbound(self, callback: Callable) -> None:
        """订阅入站消息"""
        pass
```

### 消息类型

#### InboundMessage (入站消息)
```python
@dataclass
class InboundMessage:
    channel: str          # 消息来源通道 (telegram, discord等)
    chat_id: str          # 会话ID
    message_id: str | None # 消息ID (可选)
    content: str          # 消息内容
    timestamp: datetime   # 时间戳
    metadata: dict        # 额外元数据
```

#### OutboundMessage (出站消息)
```python
@dataclass
class OutboundMessage:
    channel: str
    chat_id: str
    content: str
    reply_to: str | None
    metadata: dict
```

---

## 🔄 Part 2: 会话管理 (Session Management)

### Session 概念

**Session Key** = `channel + chat_id`

- **隔离性**：不同会话的消息不会混淆
- **持久化**：会话历史和上下文被保存
- **状态管理**：每个会话维护独立的 agent 状态

### SessionManager

```python
class SessionManager:
    def get_session(self, session_key: str) -> Session:
        """获取或创建会话"""
        pass
    
    def save_session(self, session: Session) -> None:
        """保存会话状态"""
        pass
```

### Session 结构

```python
@dataclass
class Session:
    key: str
    messages: list[dict]  # 消息历史
    context: dict         # 会话上下文
    created_at: datetime
    updated_at: datetime
```

---

## 📝 练习题

1. **概念题**
   - 解释 Session Key 的组成和作用
   - InboundMessage 和 OutboundMessage 的主要区别是什么？

2. **代码理解**
   - 查看 `MessageBus.publish_inbound()` 的实现，它如何处理消息？
   - `SessionManager.get_session()` 如何实现会话的懒加载？

3. **动手题**
   - 在 `nanobot/bus/events.py` 中添加一个新的消息类型 `SystemMessage`，用于系统通知
   - 实现一个简单的消息过滤器，在 `MessageBus` 中添加 `filter_messages()` 方法

4. **扩展思考**
   - 如果需要支持消息加密传输，你会在哪个层级实现？
   - 如何实现消息的优先级队列？

---

## 📚 学习资源

- [nanobot/bus/queue.py](nanobot/bus/queue.py) - MessageBus 实现
- [nanobot/session/manager.py](nanobot/session/manager.py) - SessionManager 实现
- [tests/test_message_bus.py](tests/test_message_bus.py) - 相关测试

开始你的第 3 周学习之旅吧！🚀