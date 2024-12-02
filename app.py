from gpt4all import GPT4All
modle = GPT4All("Meta-Llama-3-8B-Instruct.Q4_0")
output = modle.generate("the capital of France is? ")
print(output)