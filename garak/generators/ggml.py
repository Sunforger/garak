#!/usr/bin/env python3
"""ggml generator support

This generator works with ggml models in gguf format like llama.cpp.

Put the path to your ggml executable (e.g. "/home/leon/llama.cpp/main") in
an environment variable named GGML_MAIN_PATH, and pass the path to the
model you want to run either using --model_name on the command line
or as the constructor parameter when instantiating LLaMaGgmlGenerator.

Compatibility or other problems? Please let us know!
 https://github.com/leondz/garak/issues
"""


import logging
import os
import re
import subprocess

from garak import _config
from garak.generators.base import Generator

GGUF_MAGIC = bytes([0x47, 0x47, 0x55, 0x46])

class GgmlGenerator(Generator):
    """Generator interface for ggml models in gguf format.

    Set the path to the model as the model name, and put the path to the ggml executable in environment variable GGML_MAIN_PATH.
    """

    repeat_penalty = 1.1
    presence_penalty = 0.0
    frequency_penalty = 0.0
    top_k = 40
    top_p = 0.95
    temperature = 0.8
    exception_on_failure = True
    first_call = True

    generator_family_name = "ggml"

    def command_params(self):
        return {
            "-m": self.name,
            "-n": self.max_tokens,
            "--repeat-penalty": self.repeat_penalty,
            "--presence-penalty": self.presence_penalty,
            "--frequency-penalty": self.frequency_penalty,
            "--top-k": self.top_k,
            "--top-p": self.top_p,
            "--temp": self.temperature,
            "-s": self.seed,
        }


    def __init__(self, name, generations=10):
        self.path_to_ggml_main = os.getenv("GGML_MAIN_PATH")
        if self.path_to_ggml_main is None:
            raise RuntimeError("Executable not provided by environment GGML_MAIN_PATH")
        if not os.path.isfile(self.path_to_ggml_main):
            raise FileNotFoundError(f"Path provided is not a file: {self.path_to_ggml_main}")

        # this value cannot be `None`, 0 is consistent and `-1` would produce random seeds
        self.seed = _config.run.seed if _config.run.seed is not None else 0

        # model is a file, validate exists and sanity check file header for supported format
        if not os.path.isfile(name):
            raise FileNotFoundError(f"File not found, unable to load model: {name}")
        else:
            with open(name, 'rb') as model_file:
                magic_num = model_file.read(len(GGUF_MAGIC))
                if magic_num != GGUF_MAGIC:
                    raise RuntimeError(f"{name} is not in GGUF format")

        super().__init__(name, generations=generations)

    def _call_model(self, prompt):
        command = [
            self.path_to_ggml_main,
            "-p",
            prompt,
        ]
        # test all params for None type
        for key, value in self.command_params().items():
            if value is not None:
                command.append(key)
                command.append(value)
        command = [str(param) for param in command]
        if _config.system.verbose > 1:
            print("GGML invoked with", command)
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=self.exception_on_failure,
            )
            output = result.stdout.decode("utf-8")
            output = re.sub("^" + re.escape(prompt.lstrip()), "", output.lstrip())
            self.first_call = False
            return output
        except subprocess.CalledProcessError as err:
            # if this is the first call attempt, raise the exception to indicate
            # the generator is mis-configured
            print(err.stderr.decode("utf-8"))
            logging.error(err.stderr.decode("utf-8"))
            if self.first_call:
                raise err
            return None
        except Exception as err:
            logging.error(err)
            return None


default_class = "GgmlGenerator"
