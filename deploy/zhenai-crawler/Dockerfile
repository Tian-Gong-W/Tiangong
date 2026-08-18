FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -c "import base64,gzip,hashlib,pathlib; s=''.join(pathlib.Path(f'core.part{i:02d}').read_text().strip() for i in range(1,6)); assert hashlib.sha256(s.encode()).hexdigest()=='6421a155e0cde12ef39fa39aaaeb97e5abc00674ab3d36c941cd721d8d41060e', 'core checksum mismatch'; pathlib.Path('TON-MAM.py').write_bytes(gzip.decompress(base64.b64decode(s)))" \
    && sed -i 's/channel=925536/channel=904106/' TON-MAM.py \
    && sed -i 's#/426/page-frame.html#/428/page-frame.html#' TON-MAM.py \
    && sed -i 's/"heightBegin":       129/"heightBegin":       -1/' TON-MAM.py \
    && sed -i 's/"multiEducation":    ""/"multiEducation":    -1/' TON-MAM.py \
    && sed -i 's/"avatar":            -1/"avatar":            1/' TON-MAM.py \
    && sed -i 's/"zhenxin":           -1/"zhenxin":           1/' TON-MAM.py \
    && sed -i 's/"identityOk":        -1/"identityOk":        1/' TON-MAM.py \
    && sed -i 's/"loginType":         -1/"loginType":         3/' TON-MAM.py \
    && python -m py_compile TON-MAM.py run_crawler.py settings.py
CMD ["python", "run_crawler.py"]
