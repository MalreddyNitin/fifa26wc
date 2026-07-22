# gRPC service

Generate bindings with:

```powershell
python -m grpc_tools.protoc -I proto --python_out=services/grpc `
  --grpc_python_out=services/grpc proto/football_prediction.proto
python services/grpc/server.py
```
