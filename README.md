# AI-powered Hand Protection System 🛡️

![Python](https://img.shields.io/badge/Python-3.13-blue.svg)

An innovative system designed to enhance workplace safety using AI and automated document management. This project focuses on protecting workers' hands by analyzing risks and automating safety documentation.

## 📺 Watch the Demo

[Click here to watch the test video](https://github.com/kang851216/AI-powered-hand-protection-system/blob/main/test_video.mp4)

## ✨ Introduction and Detailed Feature

[Click here to download pdf](https://github.com/kang851216/AI-powered-hand-protection-system/blob/main/AI-Driven Hand Protection System.pdf)

## 🚀 Getting Started

### Prerequisites

* **Python 3.13+**
* **Pip** (Python Package Installer)

### Installation

1.  **Clone the repository**:
    ```bash
    git clone [https://github.com/kang851216/AI-powered-hand-protection-system.git](https://github.com/kang851216/AI-powered-hand-protection-system.git)
    cd AI-powered-hand-protection-system
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: Ensure `flask` and `pymupdf` are listed in your requirements file.*

## 📦 Deployment & Usage

### 1. Web Deployment (Vercel)
To deploy as a web application, ensure your files are structured for Vercel's serverless functions:
* Place your logic in `api/index.py`.
* Include a `vercel.json` file for routing.
* **Note**: Because Vercel uses a read-only file system, data is managed via integrated memory variables in the current build.

### 2. Desktop Build (PyInstaller)
To create a standalone Windows executable:
```bash
python -m PyInstaller --onefile --windowed --collect-all fitz index.py
