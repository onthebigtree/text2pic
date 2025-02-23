# 导入必要库
from flask import Flask, request, jsonify
import matplotlib
matplotlib.use('Agg')  # 解决 macOS 多线程 GUI 问题

import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO

# 设置 Matplotlib 支持中文字体
plt.rcParams['font.sans-serif'] = ['STHeiti']  # macOS 上的系统中文字体
plt.rcParams['axes.unicode_minus'] = False  # 正确显示负号

# 创建 Flask 应用
app = Flask(__name__)

# 配置常量
WEBHOOK_URL = " " # 请输入你的 Discord Webhook URL
WATERMARK_TEXT = "哈狗帮"
FONT_PATH = " "  # 字体路径

# 生成带水印的图片函数
def generate_image(text):
    # 处理换行，确保文本正确分行
    lines = [line.strip() for line in text.replace('\\n', '\n').split('\n') if line.strip()]
    
    # 设置基础参数
    FONT_SIZE = 48  # 更大的字体
    LINE_SPACING = 1.5  # 行间距倍数
    PADDING = 50  # 边距
    
    try:
        main_font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
        watermark_font = ImageFont.truetype(FONT_PATH, 72)  # 更大的水印字体
    except IOError:
        main_font = ImageFont.load_default()
        watermark_font = ImageFont.load_default()
    
    # 计算每行文本的尺寸
    line_sizes = []
    max_width = 0
    total_height = 0
    
    for line in lines:
        bbox = draw_multiline_text_getbox(line, main_font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        line_sizes.append((width, height))
        max_width = max(max_width, width)
        total_height += height
    
    # 计算图片尺寸（竖向长方形）
    line_spacing_px = int(FONT_SIZE * LINE_SPACING)
    width = max_width + (PADDING * 2)
    height = total_height + (line_spacing_px * (len(lines) - 1)) + (PADDING * 2)
    
    # 创建一个白色背景的图片
    img = Image.new('RGBA', (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # 绘制水印（斜向，半透明，在文字后面）
    watermark_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    watermark_draw = ImageDraw.Draw(watermark_layer)
    
    # 计算水印旋转和位置
    watermark_img = Image.new('RGBA', (width * 2, height * 2), (0, 0, 0, 0))
    watermark_draw = ImageDraw.Draw(watermark_img)
    
    # 绘制多个交错的水印
    for i in range(-2, 3):
        y_offset = i * height // 2
        watermark_draw.text(
            (width // 2, height + y_offset),
            WATERMARK_TEXT,
            font=watermark_font,
            fill=(255, 192, 203, 60),  # 粉红色半透明
            anchor="mm"
        )
    
    # 旋转水印层
    watermark_img = watermark_img.rotate(45, expand=True)
    
    # 裁剪并粘贴到主图层
    watermark_img = watermark_img.crop((width//2, height//2, width*3//2, height*3//2))
    img.paste(watermark_img, (0, 0), watermark_img)
    
    # 绘制主文本
    current_y = PADDING
    for i, line in enumerate(lines):
        bbox = draw_multiline_text_getbox(line, main_font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        
        # 绘制文本阴影
        shadow_offset = 2
        draw.text((x + shadow_offset, current_y + shadow_offset), line, 
                 font=main_font, fill=(128, 128, 128, 180))
        
        # 绘制主文本
        draw.text((x, current_y), line, font=main_font, fill=(0, 0, 0, 255))
        
        current_y += line_sizes[i][1] + line_spacing_px
    
    # 保存图片到缓冲区
    final_buffer = BytesIO()
    img.save(final_buffer, format='PNG', quality=95)
    final_buffer.seek(0)
    return final_buffer

def draw_multiline_text_getbox(text, font):
    """获取多行文本的边界框"""
    # 创建临时图像和绘图对象来计算文本大小
    temp_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)
    return temp_draw.textbbox((0, 0), text, font=font)

# 发送图片到 Discord Webhook
def send_to_discord(image_buffer):
    files = {"file": ("output.png", image_buffer, "image/png")}
    response = requests.post(WEBHOOK_URL, files=files)
    return response.status_code

# 创建测试路由
@app.route('/test', methods=['GET'])
def test_image():
    try:
        test_text = "这是标题\n这是第二行\n这是第三行\n很长的一段文字\n测试换行效果\n哈狗帮"
        image_buffer = generate_image(test_text)
        status_code = send_to_discord(image_buffer)
        
        if status_code == 204:
            return jsonify({
                "message": "测试成功！图片已发送到 Discord",
                "status_code": status_code
            }), 200
        else:
            return jsonify({
                "error": "发送失败",
                "status_code": status_code
            }), 500
    except Exception as e:
        return jsonify({
            "error": "测试过程中发生错误",
            "details": str(e)
        }), 500

# 改进主路由的错误处理
@app.route('/send-image', methods=['POST'])
def send_image():
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "请传入有效的文案 (text)。"}), 400

        text = data['text']
        if not text.strip():
            return jsonify({"error": "文案不能为空。"}), 400

        image_buffer = generate_image(text)
        status_code = send_to_discord(image_buffer)

        if status_code == 204:
            return jsonify({"message": "图片已成功发送到 Discord Webhook。"}), 200
        else:
            return jsonify({"error": f"发送失败，Discord 返回状态码: {status_code}"}), 500
    except Exception as e:
        return jsonify({
            "error": "处理请求时发生错误",
            "details": str(e)
        }), 500

# 启动 Flask 服务器
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5302, debug=True)
