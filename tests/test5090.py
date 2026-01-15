import torch
import esm  # 现在应该能成功导入了

print(f"CUDA: {torch.cuda.is_available()}")
# 再次确认识别的是 5090
print(f"Device: {torch.cuda.get_device_name(0)}")