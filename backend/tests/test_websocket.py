import pytest
from unittest.mock import AsyncMock
from backend.api.websocket_manager import ConnectionManager

@pytest.mark.asyncio
async def test_websocket_manager_flow():
    manager = ConnectionManager()
    
    # Mock WebSocket object
    mock_ws = AsyncMock()
    
    # 1. Test Connect
    await manager.connect(mock_ws)
    assert len(manager.active_connections) == 1
    
    # 2. Test Broadcast
    await manager.broadcast({"message": "test"})
    mock_ws.send_json.assert_called_with({"message": "test"})
    
    # 3. Test Disconnect
    manager.disconnect(mock_ws)
    assert len(manager.active_connections) == 0
