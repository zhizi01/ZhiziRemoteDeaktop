import asyncio
import websockets
import json
import base64
from PIL import Image
from io import BytesIO
from mss import mss

sessionUUID = ""

async def SendScreen(websocket):
    """
    发送屏幕截图
    """
    with mss() as sct:
        screenshot = sct.shot(mon=1, output="1.png")
        
        with Image.open(screenshot) as img:
            with BytesIO() as output:
                img.save(output, format="JPEG")
                jpg_base64 = base64.b64encode(output.getvalue()).decode('utf-8')

    await websocket.send(json.dumps({
        "type": "newsletter",
        "uuid": sessionUUID,
        "data": {
            "type": "desktopScreen",
            "screen": jpg_base64
        }
    }))

async def HandleConnection(websocket, path):
    global sessionUUID  # 声明全局变量
    print("连接到服务器...")

    try:
        await websocket.send(json.dumps({"type": "auth", "group": "user"}))
        async for message in websocket:
            data = json.loads(message)
            print("消息数据: ", data)

            if data.get("code") == "200":
                ResultData = data.get("result")
                if ResultData["type"] == "authResponse":
                    sessionUUID = ResultData["uuid"]
                elif ResultData["type"] in ["desktopScreen","desktopConnect"] and ResultData["message"] in ["start", "next"]:
                    
                    await SendScreen(websocket)
                else:
                    print("未知指令 -> ", data)
            else:
                print("发生错误 -> ", data)

    except websockets.exceptions.ConnectionClosedError:
        print("已与服务器断开连接!")
    except Exception as e:
        print(f"处理消息时发生异常: {e}")

async def Main():
    uri = "ws://127.0.0.1:8765"
    async with websockets.connect(uri) as websocket:
        await HandleConnection(websocket, None)

if __name__ == "__main__":
    asyncio.run(Main())
