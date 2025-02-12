# [kubectl](https://kubernetes.io/zh-cn/docs/tasks/tools/install-kubectl-linux/)
For Ubuntu
```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl.sha256"
echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check  # output: kubectl: OK
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
kubectl version --client
```

# [Minikube](https://minikube.sigs.k8s.io/docs/start/?arch=%2Flinux%2Fx86-64%2Fstable%2Fdebian+package)
## installation
For Ubuntu
```bash
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube_latest_amd64.deb
sudo dpkg -i minikube_latest_amd64.deb

```

## Start your cluster
From a terminal with administrator access (but not logged in as root), run:
```
minikube start
```
## Interact with your cluster
If you already have kubectl installed (see documentation), you can now use it to access your shiny new cluster:
```bash
kubectl get po -A
```
[hello minikube](https://kubernetes.io/zh-cn/docs/tutorials/hello-minikube/)


# 1 使用Minikube进行本地测试

## 1.1 启动本地Kubernetes 集群

```bash
minikube start  
```

## 1.2 加载镜像到本地集群
```bash
minikube image load my-csi-driver:latest  
```

### 1.3 编写 Kubernetes 部署文件

创建一个 Kubernetes 部署文件（如 deployment.yaml），用于部署你的 CSI 驱动。以下是一个简单的示例：

```yaml
apiVersion: apps/v1  
kind: Deployment  
metadata:  
  name: my-csi-driver  
spec:  
  replicas: 1  
  selector:  
    matchLabels:  
      app: my-csi-driver  
  template:  
    metadata:  
      labels:  
        app: my-csi-driver  
    spec:  
      containers:  
      - name: my-csi-driver  
        image: my-csi-driver:latest  
        imagePullPolicy: IfNotPresent
```

### 1.4 部署并测试

使用 kubectl 部署你的 CSI 驱动：

```bash
kubectl apply -f deployment.yaml  
```
检查 Pod 是否成功启动：

```bash
kubectl get pods
```  
查看 Pod 日志以确认 CSI 驱动是否正常运行：

```bash
kubectl logs <pod_name> 
``` 

### 1.5 验证 CSI 功能
要确保 PVC 使用你的 CSI 驱动，你需要明确指定 StorageClass，并确保 StorageClass 的 provisioner 字段指向你的 CSI 驱动。以下是解决这个问题的步骤：

#### 1.5.1 创建自定义 StorageClass

创建一个 StorageClass，并将 provisioner 字段设置为你的 CSI 驱动的名称。例如，如果你的 CSI 驱动名称是 my-csi-driver，可以创建如下 StorageClass：
```yaml
apiVersion: storage.k8s.io/v1  
kind: StorageClass  
metadata:  
  name: my-csi-storageclass  
provisioner: my-csi-driver 
``` 
保存为 storageclass.yaml，然后应用：

```bash
kubectl apply -f storageclass.yaml 
``` 
#### 1.5.2 修改 PVC 以使用自定义 StorageClass
在 PVC 中显式指定 storageClassName 为你刚刚创建的 my-csi-storageclass。例如：

```yaml
apiVersion: v1  
kind: PersistentVolumeClaim  
metadata:  
  name: my-pvc  
spec:  
  accessModes:  
    - ReadWriteOnce  
  resources:  
    requests:  
      storage: 1Gi  
  storageClassName: my-csi-storageclass 
``` 
保存为 pvc.yaml，然后应用：

```bash
kubectl apply -f pvc.yaml 
``` 
#### 1.5.3 验证 PVC 和 PV 的关联
再次检查 PVC 和 PV 的状态，确认它们是否使用了你的 CSI 驱动。

检查 PVC 状态：
```bash
kubectl get pvc my-pvc -o yaml
```  
在输出中，检查 spec.storageClassName 是否为 my-csi-storageclass，并确认 spec.volumeName 是否指向一个 PV。

检查 PV 状态：
```bash
kubectl get pv <pv-name> -o yaml  
```
在输出中，检查 spec.csi.driver 是否为 my-csi-driver，并确认 spec.storageClassName 是否为 my-csi-storageclass。

#### 1.5.4. 检查 CSI 驱动的日志
查看 CSI 驱动的日志，确认是否有与 PVC 相关的操作（如 CreateVolume）：

```bash
kubectl logs <csi-driver-pod-name>  
```
如果你看到类似 CreateVolume 的日志条目，说明你的 CSI 驱动已经正确处理了 PVC 请求。


## 1.6 清理资源
测试完成后，记得清理资源：

```bash
kubectl delete -f deployment.yaml
kubectl delete -f storageclass.yaml
kubectl delete -f pvc.yaml  
```