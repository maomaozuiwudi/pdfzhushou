# PDF助手 PDF Assistant

PDF全能处理工具，9大功能：合并、拆分、提取、转换、加密、压缩、水印、图片转PDF、OCR文字识别。

## 功能特性

- **PDF合并** - 将多个PDF文件合并为一个PDF，支持拖拽排序
- **PDF拆分** - 按页码范围或每N页拆分为独立文件
- **提取页面** - 从PDF中提取指定页码范围，支持缩略图点选
- **格式转换** - PDF转PNG/JPEG图片，PDF转Word (.docx)
- **加密解密** - 为PDF添加AES-256密码保护，或移除已有密码
- **PDF压缩** - 三级压缩（轻度/标准/极限），有效减小文件体积
- **水印添加** - 文字水印（自定义文字/颜色/位置/透明度）和图片水印
- **图片转PDF** - 将多张图片合并转换为PDF
- **OCR文字识别** - 扫描件/图片PDF转纯文本，支持中英文混合识别

## 安装

```bash
pip install -r requirements.txt
```

**OCR功能需要额外安装 Tesseract OCR：**
- 下载地址：https://github.com/UB-Mannheim/tesseract/wiki
- 安装时勾选中文语言包 (Chinese Simplified)
- 默认安装路径 `C:\Program Files\Tesseract-OCR\` 即可自动识别

## 运行

```bash
python 启动器.py
```

## 依赖

- PyMuPDF (fitz) - PDF渲染和操作
- pikepdf - PDF加密/解密/压缩
- Pillow - 图片处理
- pytesseract - OCR文字识别（可选）
- pdf2docx - PDF转Word（可选）

## 许可证

MIT License
