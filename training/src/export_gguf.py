"""
Merge LoRA adapter into base model and export as AWQ for vLLM serving.
Run after training completes.
"""
import argparse
import os

from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer


def main(adapter_path: str, output_path: str):
    print(f"Loading LoRA adapter from {adapter_path}")
    model = AutoPeftModelForCausalLM.from_pretrained(
        adapter_path,
        device_map="auto",
        torch_dtype="auto",
    )
    tokenizer = AutoTokenizer.from_pretrained(adapter_path)

    print("Merging LoRA weights into base model...")
    merged = model.merge_and_unload()

    print(f"Saving merged model to {output_path}")
    merged.save_pretrained(output_path, safe_serialization=True)
    tokenizer.save_pretrained(output_path)

    print(f"""
Merged model saved to: {output_path}

Next steps to quantize and serve with vLLM:
  1. Quantize to AWQ:
     pip install autoawq
     python -c "
     from awq import AutoAWQForCausalLM
     model = AutoAWQForCausalLM.from_pretrained('{output_path}')
     model.quantize(tokenizer, quant_config={{'zero_point': True, 'q_group_size': 128, 'w_bit': 4, 'version': 'GEMM'}})
     model.save_quantized('{output_path}-awq')
     "
  2. Update vllm-cm.yaml MODEL_ID to point to your local path or push to HuggingFace Hub
  3. Restart vLLM deployment: kubectl -n ai-voice rollout restart deploy/vllm
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", default="/models/lora-adapter")
    parser.add_argument("--output", default="/models/merged-model")
    args = parser.parse_args()
    main(args.adapter, args.output)
