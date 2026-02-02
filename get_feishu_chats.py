import requests
import json
import argparse

def get_tenant_access_token(app_id, app_secret):
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = {
        "app_id": app_id,
        "app_secret": app_secret
    }
    response = requests.post(url, json=data, headers=headers)
    return response.json().get("tenant_access_token")

def list_chats(token):
    url = "https://open.feishu.cn/open-apis/im/v1/chats"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"page_size": 20}  # 获取最近的20个群
    
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    
    if data.get("code") == 0:
        items = data.get("data", {}).get("items", [])
        print(f"\n成功获取到 {len(items)} 个群组:\n")
        print(f"{'群组名称':<30} | {'Chat ID (复制这个)':<40}")
        print("-" * 75)
        for chat in items:
            name = chat.get("name", "未命名群组")
            chat_id = chat.get("chat_id")
            print(f"{name:<30} | {chat_id:<40}")
        print("-" * 75)
    else:
        print(f"获取群组失败: {data}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='获取飞书群组ID工具')
    parser.add_argument('--app-id', required=True, help='飞书 App ID')
    parser.add_argument('--app-secret', required=True, help='飞书 App Secret')
    args = parser.parse_args()
    
    print("正在获取 Token...")
    token = get_tenant_access_token(args.app_id, args.app_secret)
    
    if token:
        print("Token 获取成功，正在查询群列表...")
        list_chats(token)
    else:
        print("Token 获取失败，请检查 ID 和 Secret")
