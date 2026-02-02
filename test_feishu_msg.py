import requests
import json
import argparse
import time

def get_tenant_access_token(app_id, app_secret):
    """获取飞书 Tenant Access Token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = {
        "app_id": app_id,
        "app_secret": app_secret
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)
        res = response.json()
        if res.get("code") == 0:
            print("✅ Token 获取成功")
            return res.get("tenant_access_token")
        else:
            print(f"❌ Token 获取失败: {res.get('msg')}")
            return None
    except Exception as e:
        print(f"❌ 网络请求异常: {e}")
        return None

def send_test_message(token, chat_id):
    """发送测试消息"""
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    msg_content = {
        "text": f"👋 飞书消息测试成功！\n------------------\n⏱️ 时间: {current_time}\n🆔 群组: {chat_id}\n🤖 机器人状态: 正常"
    }
    
    data = {
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps(msg_content)
    }

    try:
        print(f"📤 正在向群组 {chat_id} 发送消息...")
        response = requests.post(url, json=data, headers=headers, timeout=10)
        res = response.json()
        
        if res.get("code") == 0:
            print("✅ 消息发送成功！请查看飞书群组。")
            return True
        else:
            err_code = res.get("code")
            err_msg = res.get("msg")
            print(f"❌ 发送失败 (代码 {err_code}): {err_msg}")
            
            if err_code == 230001:
                print("💡 提示: 可能是因为机器人没有被拉入该群组，或者没有发送消息的权限。")
            elif err_code == 99991668:
                print("💡 提示: 可能是应用并未发布版本，或者权限未通过审核。")
            return False
            
    except Exception as e:
        print(f"❌ 发送异常: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='飞书消息发送测试工具')
    parser.add_argument('--app-id', required=True, help='飞书 App ID')
    parser.add_argument('--app-secret', required=True, help='飞书 App Secret')
    parser.add_argument('--chat-id', required=True, help='目标群组 Chat ID')
    
    args = parser.parse_args()
    
    print("🚀 开始飞书连接测试...")
    token = get_tenant_access_token(args.app_id, args.app_secret)
    
    if token:
        send_test_message(token, args.chat_id)
