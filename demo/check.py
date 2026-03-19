import paddle
print(paddle.utils.run_check())
print("GPU available:", paddle.is_compiled_with_cuda())
print("Device count:", paddle.device.get_device())