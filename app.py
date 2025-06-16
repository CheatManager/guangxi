import re
import io
import zipfile
from flask import Flask, request, jsonify, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests

app = Flask(__name__)

# 初始化限制器（每分钟5次）
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["5 per minute"]
)

# 全局变量存储 Cookie（Render 会持久化）
current_cookie = ""

# 公共 Headers
headers_first = {
    "Host": "www.gxdlys.com",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; MEIZU 21 Build/UKQ1.230917.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/134.0.6998.136 Mobile Safari/537.36 XWEB/1340129 MMWEBSDK/20250201 MMWEBID/54 MicroMessenger/8.0.58.2840(0x28003A52) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "http://www.gxdlys.com/Wechat/EcertCert/ECertApply?OperateType=0&BnsAcceptId=&ObjectId=&BasicBnsId=46011&Params=%E7%BB%8F%E8%90%A5%E6%80%A7%E9%81%93%E8%B7%AF%E8%B4%A7%E7%89%A9%E8%BF%90%E8%BE%93%E9%A9%BE%E9%A9%B6%E5%91%98&Step=1",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cookie": current_cookie
}

headers_second = headers_first.copy()
headers_second.update({
    "Accept": "image/wxpic,image/tpg,image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "X-Requested-With": "com.tencent.mm"
})

def validate_id_card(id_card):
    """验证身份证号格式"""
    return re.match(r"^\d{15,18}[Xx]?$", id_card)

@app.route('/api/query', methods=['GET'])
@limiter.limit("5 per minute")
def query():
    name = request.args.get('name')
    id_card = request.args.get('id_card')
    
    if not name or not id_card:
        return jsonify({"error": "姓名和身份证号不能为空"}), 400
    
    if not validate_id_card(id_card):
        return jsonify({"error": "身份证号格式不正确"}), 400
    
    try:
        # 更新 headers 中的 cookie
        headers_first['Cookie'] = current_cookie
        headers_second['Cookie'] = current_cookie
        
        print(f"正在查询：{id_card} {name}")
        url_first = f"http://www.gxdlys.com/Wechat/FaceDetect/GetGAIDCardPhotoNew?idCard={id_card}&name={name}"
        response_first = requests.get(url_first, headers=headers_first)
        response_json = response_first.json()

        if response_json.get("statusCode") != 200:
            return jsonify({"error": "身份证查询失败", "details": response_json}), 400

        item1 = response_json["data"]["item1"]  # 图片ID
        item2 = response_json["data"]["item2"]  # 身份证信息

        # 构建身份证信息字符串
        info_str = (
            f"姓名：{item2['name']}\n"
            f"身份证号：{item2['pid']}\n"
            f"性别：{item2['gender']}\n"
            f"民族：{item2['nation']}\n"
            f"出生日期：{item2['dob']}\n"
            f"详细地址：{item2['fulladdr']}\n"
            f"身份证办理地：{item2['issueD_UNIT']}\n"
            f"身份证有效开始日期：{item2['uL_FROM_DATE']}\n"
            f"身份证有效结束日期：{item2['uL_END_DATE']}\n"
            f"身份证有效期：{item2['usefuL_LIFE']}\n"
        )

        # 获取身份证图片
        url_second = f"http://www.gxdlys.com/System/FileService/ShowFile?fileId={item1}"
        response_second = requests.get(url_second, headers=headers_second)

        if response_second.status_code != 200:
            return jsonify({"error": "身份证图片下载失败"}), 400

        # 创建内存中的ZIP文件
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr(f"{name}_身份证信息.txt", info_str.encode('utf-8'))
            zip_file.writestr(f"{name}_身份证照片.jpg", response_second.content)
        
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{name}_身份证信息.zip"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/update_cookie', methods=['POST'])
def update_cookie():
    global current_cookie
    new_cookie = request.json.get('cookie')
    if not new_cookie:
        return jsonify({"error": "Cookie不能为空"}), 400
    
    current_cookie = new_cookie
    return jsonify({"message": "Cookie更新成功"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)  # Render 默认用 10000 端口
