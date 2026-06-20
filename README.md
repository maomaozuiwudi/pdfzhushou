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

## ❓ 常见问题 (FAQ)

<details>
<summary><b>PDF助手能免费商用吗？</b></summary>

能。PDF助手基于 MIT 协议开源，个人和企业都可以自由使用、修改、再分发，无需任何授权费用。
</details>

<details>
<summary><b>支持批量处理多个PDF吗？</b></summary>

支持。合并、拆分、压缩、水印、图片转PDF等功能均支持批量操作，拖拽或选中多个文件即可一键处理。
</details>

<details>
<summary><b>OCR识别准确率怎么样？</b></summary>

目前集成 Tesseract OCR，中英文混合识别效果良好。如需更高精度，可自行替换为 PaddleOCR 等引擎。清晰文档下识别率可达 95%+。
</details>

<details>
<summary><b>和Adobe Acrobat/PDF-Guru比有什么优势？</b></summary>

相比 Adobe Acrobat：完全免费、轻量（纯 Python 实现）、无需注册。相比 PDF-Guru：代码开源透明、MIT 协议更宽松、支持 OCR 和加密等更全面的功能。
</details>

<details>
<summary><b>能保护PDF不被复制/打印吗？</b></summary>

能。支持 AES-256 加密，可设置用户密码和所有者密码，限制打印、复制、修改等权限。
</details>

<details>
<summary><b>支持PDF转Word/WPS文档吗？</b></summary>

支持。基于 pdf2docx 引擎，可将 PDF 转换为 Word (.docx) 格式，保留基本排版。转换后可在 WPS、Office 中直接编辑。
</details>

<details>
<summary><b>需要安装Tesseract OCR吗？</b></summary>

如需使用 OCR 功能（图片转PDF、扫描件识别），需要额外安装 Tesseract OCR 引擎。软件只用到文字提取时则无需安装。
</details>

## 许可证

MIT License

---

> 🤖 **更多AI工具推荐 → 关注小红书 @工具箱里的猫**  
> 发现好用免费的Windows桌面工具、AI搜索技巧、效率神器，每天更新。
