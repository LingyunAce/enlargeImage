# EnlargeImage Backend

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Download SwinIR weights

```bash
mkdir -p models
# X4 model (default)
curl -L -o models/SwinIR_REALSR_X4.pth https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/003_realSR_BSRGAN_DFO_s64w8_SwinIR-M_x4_GAN.pth
# X2 (optional)
curl -L -o models/SwinIR_REALSR_X2.pth https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/002_lightweightSR_DIV2K_s64w8_SwinIR-S_x2.pth
# X8 (optional)
curl -L -o models/SwinIR_REALSR_X8.pth https://github.com/JingyunLiang/SwinIR/releases/download/v0.0/001_classicalSR_DIV2K_s48w8_SwinIR-M_x8.pth
```

> If only X4 is present, requests for `scale=2` or `scale=8` will return 503.

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

## Test

```bash
pytest -x
```
