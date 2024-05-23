import asyncio
import websockets
import json
import uuid
from orm import OnlineUser, Session, SessionLocal, engine, or_

connMarkToWebsocket = {}
WebSocketForUUid = {}

async def handleDesktopConnect(websocket, data, uuid):
    """
    发送开始屏幕处理
    """

    # 先检查目标的UUID是否存在
    clientUUID = data.get("client")

    if clientUUID not in connMarkToWebsocket:
        response = {"code": "403", "result": {"type": "desktopConnect", "message": "客户不存在或已离线!"}}
        await websocket.send(json.dumps(response))
        return
    
    # 存在则检查权限
    onlineDB = SessionLocal()
    clientInDB = onlineDB.query(OnlineUser).filter_by(uuid=uuid).first()
    
    if clientInDB is None or clientInDB.identities != "service":
        response = {"code": "403", "result": {"type": "desktopConnect", "message": "客户不存在或权限错误!"}}
        await websocket.send(json.dumps(response))
        onlineDB.close()
        return
    
    # 合法,建立连接
    if onlineDB.query(Session).filter_by(client_uuid=clientUUID).count() < 1:
        # 没有在被查看中就发送开启查看,先写到库里

        onlineObject = Session(service_uuid=uuid, client_uuid=clientUUID)
        onlineDB.add(onlineObject)
        onlineDB.commit()
        onlineDB.close()

        # 向客户发送开始指令

        clientWebSocket = connMarkToWebsocket[clientUUID]
        clientResponse = {"code": "200", "result": {"type": "desktopConnect", "message": "start"}}

        response = {"code": "200", "result": {"type": "desktopConnect", "message": "连接建立已发送!"}}
        await websocket.send(json.dumps(response))
        await clientWebSocket.send(json.dumps(clientResponse))
    else:
        # 有被查看中,加入查看

        onlineObject = Session(service_uuid=uuid, client_uuid=clientUUID)
        onlineDB.add(onlineObject)
        onlineDB.commit()
        onlineDB.close()

        response = {"code": "200", "result": {"type": "desktopConnect", "message": "连接建立已发送!"}}
        await websocket.send(json.dumps(response))


async def handleDesktopSession(websocket, uuid, data):
    """
    处理桌面会话
    """

    onlineDB = SessionLocal()
    serviceList = onlineDB.query(Session).filter_by(client_uuid=uuid).all()
    onlineDB.close()

    response = {"code": "200", "result": {"type": "desktopScreen", "screen": data.get("screen")}}

    for service in serviceList:
        # 循环发送
        ServiceWebsocket = connMarkToWebsocket[service.service_uuid]
        await ServiceWebsocket.send(json.dumps(response))

    # 获取下一帧
    if len(serviceList) > 0:
        await websocket.send(json.dumps({"code": "200", "result": {"type": "desktopScreen", "message": "next"}}))


async def handleNewsletter(websocket, data, uuid):
    """
    处理消息
    """

    newsletterData = data.get("data")
    messageType = newsletterData.get("type")

    if messageType == "desktopScreen":
        await handleDesktopSession(websocket, uuid, newsletterData)
    elif messageType == "desktopConnect":
        await handleDesktopConnect(websocket, newsletterData, uuid)
    else:
        response = {"code": "403", "result": {"type": "newsletterResponse", "message": "未知指令!"}}
        await websocket.send(json.dumps(response))


async def authenticateConnection(websocket, data):
    """
    处理认证连接，分配UUID
    """
    group = data.get('group')
    if group not in ['user', 'service']:
        response = {"code": "404", "result": {"type": "authResponse", "message": "通讯数据异常,已终止通讯!"}}
        await websocket.send(json.dumps(response))
        await websocket.close()
        return

    newUuid = str(uuid.uuid4())
    if newUuid not in connMarkToWebsocket:
        connMarkToWebsocket[newUuid] = websocket
        WebSocketForUUid[websocket] = newUuid

        onlineDB = SessionLocal()
        onlineObject = OnlineUser(uuid=newUuid, identities=group)
        onlineDB.add(onlineObject)
        onlineDB.commit()
        onlineDB.close()

        response = {"code": "200", "result": {"type": "authResponse", "uuid": newUuid}}
        await websocket.send(json.dumps(response))
    else:
        response = {"code": "403", "result": {"type": "authResponse", "message": "连接已经建立,无法再次创建!"}}
        await websocket.send(json.dumps(response))


async def handleConnClose(websocket):
    """
    处理连接关闭事件
    """
    if websocket in WebSocketForUUid:
        # 从变量表中移除

        ConnUUID = WebSocketForUUid[websocket]

        del connMarkToWebsocket[ConnUUID]
        del WebSocketForUUid[websocket]

        # 从数据库中移除
        onlineDB = SessionLocal()
        onlineDB.query(OnlineUser).filter_by(uuid=ConnUUID).delete()
        onlineDB.query(Session).filter(or_(Session.service_uuid == ConnUUID, Session.client_uuid == ConnUUID)).delete()
        onlineDB.commit()
        onlineDB.close()




async def handleConnection(websocket, path):
    """
    处理数据
    """
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                handleType = data.get("type")
                if handleType == "auth":
                    await authenticateConnection(websocket, data)
                elif handleType == "newsletter":
                    uuid = data.get("uuid")
                    if uuid in connMarkToWebsocket and connMarkToWebsocket[uuid] == websocket:
                        await handleNewsletter(websocket, data, uuid)
                    else:
                        response = {"code": "403", "result": {"type": "authResponse", "message": "通讯认证错误,请重新建立连接!"}}
                        await websocket.send(json.dumps(response))
                        await websocket.close()
                else:
                    response = {"code": "404", "result": {"type": "authResponse", "message": "异常的消息类型!"}}
                    await websocket.send(json.dumps(response))
            except json.JSONDecodeError:
                response = {"code": "500", "result": {"type": "authResponse", "message": "通讯发生错误,请重新建立连接!"}}
                await websocket.send(json.dumps(response))
                await websocket.close()
    finally:
        # 处理连接关闭事件
        await handleConnClose(websocket)


# 启动WebSocket服务器
async def main():
    """
    启动WebSocket服务器
    """
    async with websockets.serve(handleConnection, "localhost", 8765,max_size=10*1024*1024):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
