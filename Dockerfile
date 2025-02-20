FROM python:3.10-slim  
WORKDIR /app  
COPY . .  
RUN pip install -r requirements.txt 

# 设置固定入口点（ENTRYPOINT不可被覆盖）
ENTRYPOINT ["python", "/app/server.py"]

# 设置默认参数（这些参数会被K8s yaml中的args覆盖）
CMD ["--drivername=default.csi.k8s.io", "--v=3"]