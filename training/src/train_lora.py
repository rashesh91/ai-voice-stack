"""
QLoRA fine-tuning of Llama 3.1 8B on Indian language call transcripts.
Uses TRL SFTTrainer with PEFT LoRA adapters.
"""
import argparse
import os
import yaml

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTTrainer, SFTConfig


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main(config_path: str):
    cfg = load_config(config_path)
    model_cfg = cfg["model"]
    lora_cfg = cfg["lora"]
    train_cfg = cfg["training"]
    data_cfg = cfg["data"]

    print(f"Loading base model: {model_cfg['base_model']}")

    model = AutoModelForCausalLM.from_pretrained(
        model_cfg["base_model"],
        dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_cfg["base_model"], trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    lora_config = LoraConfig(
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["lora_alpha"],
        lora_dropout=lora_cfg["lora_dropout"],
        bias=lora_cfg["bias"],
        task_type=lora_cfg["task_type"],
        target_modules=lora_cfg["target_modules"],
    )

    dataset = load_dataset("json", data_files={"train": data_cfg["train_file"]}, split="train")
    n_val = max(1, int(len(dataset) * data_cfg["val_split"]))
    dataset = dataset.train_test_split(test_size=n_val)

    n_train = len(dataset["train"])
    warmup_steps = max(1, int(n_train * train_cfg["num_train_epochs"] * train_cfg["warmup_ratio"]
                              / train_cfg["gradient_accumulation_steps"]))

    training_args = SFTConfig(
        output_dir=train_cfg["output_dir"],
        num_train_epochs=train_cfg["num_train_epochs"],
        per_device_train_batch_size=train_cfg["per_device_train_batch_size"],
        gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
        learning_rate=train_cfg["learning_rate"],
        lr_scheduler_type=train_cfg["lr_scheduler_type"],
        warmup_steps=warmup_steps,
        logging_steps=train_cfg["logging_steps"],
        save_steps=train_cfg["save_steps"],
        fp16=train_cfg["fp16"],
        bf16=train_cfg["bf16"],
        optim=train_cfg["optim"],
        dataloader_num_workers=train_cfg["dataloader_num_workers"],
        max_length=train_cfg["max_seq_length"],
        report_to="none",
    )

    def formatting_func(example):
        return tokenizer.apply_chat_template(
            example["messages"], tokenize=False, add_generation_prompt=False
        )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        processing_class=tokenizer,
        formatting_func=formatting_func,
        peft_config=lora_config,
    )

    print("Starting training...")
    trainer.train()
    trainer.save_model(train_cfg["output_dir"])
    tokenizer.save_pretrained(train_cfg["output_dir"])
    print(f"LoRA adapter saved to {train_cfg['output_dir']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    main(args.config)
