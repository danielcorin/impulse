import argparse
import base64
import importlib
import json
import sys
from pathlib import Path
from typing import Any, List, Optional
import httpx

from google.protobuf.json_format import Parse
from openai import OpenAI
import anthropic
import fitz  # PyMuPDF
from PIL import Image
import io

PROMPT = """{schema}
Using the provided content and images, extract data as JSON in adherence to the above schema.
If multiple pages or images are provided, combine the information into a single JSON object.
No talk. JSON only.
"""


class FileContainer:
    def __init__(self):
        self.pages: List[bytes] = []
        self.image_type: str = "jpeg"

    def add_page(self, page_bytes: bytes):
        self.pages.append(page_bytes)

    def set_image_type(self, image_type: str):
        if image_type.lower() == "jpg":
            self.image_type = "jpeg"
        else:
            self.image_type = image_type


def unpack_json_to_proto(json_data: str, target_obj: str, module) -> Any:
    """
    Unpacks JSON data into a protobuf object.

    Args:
    json_data (str): JSON string to unpack.
    target_obj (str): Name of the protobuf class.
    module: The dynamically imported protobuf module.

    Returns:
    Any: An instance of the specified protobuf class with data from the JSON.
    """
    # Get the protobuf class from the module
    proto_class = getattr(module, target_obj)

    # Parse JSON string to dict
    data_dict = json.loads(json_data)

    # Create a new instance of the protobuf class
    proto_instance = proto_class()

    # Use the Parse function to populate the protobuf instance
    Parse(json.dumps(data_dict), proto_instance)

    return proto_instance


def main(args: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Process a receipt from an image or PDF."
    )
    parser.add_argument("--proto", type=str, help="The proto file path")
    parser.add_argument(
        "--file_path",
        type=str,
        help="Path to the receipt image or PDF, or URL to download from",
    )
    parser.add_argument(
        "--model",
        type=str,
        choices=["openai", "anthropic"],
        default="openai",
        help="The model to use for extraction (openai or anthropic)",
    )

    if args is None:
        args = sys.argv[1:]

    parsed_args = parser.parse_args(args)

    # Read the proto file
    path, target_obj = parsed_args.proto.split(":")
    proto_path = Path(path)
    with proto_path.open("r") as proto_file:
        schema = proto_file.read()

    # Dynamically import the generated code
    module_name = proto_path.stem + "_pb2"
    gen_path = Path("gen") / proto_path.relative_to(proto_path.anchor)
    gen_path = gen_path.with_name(module_name + ".py")
    spec = importlib.util.spec_from_file_location(module_name, str(gen_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Now we can use the imported module and the schema
    file_container = process_file(parsed_args.file_path)
    result = extract_from_file_container(file_container, schema, parsed_args.model)
    result = result.replace("```json", "").replace("```", "")
    print("Extracted JSON:")
    print(result)

    if result:
        proto_instance = unpack_json_to_proto(result, target_obj, module)
        print("Proto instance:")
        print(proto_instance)


def process_file(file_path: str) -> FileContainer:
    file_container = FileContainer()

    if file_path.lower().startswith(("http://", "https://")):
        with httpx.Client() as client:
            response = client.get(file_path)
            response.raise_for_status()
            content = response.content
        file_container.add_page(content)
        file_container.set_image_type(Path(file_path).suffix[1:] or "jpeg")
    elif file_path.lower().endswith(".pdf"):
        pdf_document = fitz.open(file_path)
        for page in pdf_document:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Increase resolution by 2x
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format="PNG", quality=95)  # Increase quality
            file_container.add_page(img_byte_arr.getvalue())
        pdf_document.close()
        file_container.set_image_type("png")
    else:
        with open(file_path, "rb") as image_file:
            file_container.add_page(image_file.read())
        file_container.set_image_type(Path(file_path).suffix[1:])

    return file_container


def extract_from_file_container(
    file_container: FileContainer, schema: str, model: str
) -> Optional[str]:
    if model == "openai":
        return extract_from_file_container_openai(file_container, schema)
    elif model == "anthropic":
        return extract_from_file_container_anthropic(file_container, schema)
    else:
        raise ValueError(f"Unsupported model: {model}")


def extract_from_file_container_openai(
    file_container: FileContainer, schema: str
) -> Optional[str]:
    # Initialize the OpenAI client
    client = OpenAI()

    # Encode the images
    encoded_images = [
        base64.b64encode(img).decode("utf-8") for img in file_container.pages
    ]

    # Prepare the content for the API call
    content = [
        {
            "type": "text",
            "text": PROMPT.format(schema=schema),
        }
    ]
    for encoded_image in encoded_images:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/{file_container.image_type};base64,{encoded_image}"
                },
            }
        )

    messages = [
        {
            "role": "user",
            "content": content,
        }
    ]
    # Make the API call to OpenAI
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
        )

        return response.choices[0].message.content
    except Exception as e:
        print(f"An error occurred during OpenAI API call: {e}")
        return None


def extract_from_file_container_anthropic(
    file_container: FileContainer, schema: str
) -> Optional[str]:
    # Initialize the Anthropic client
    client = anthropic.Anthropic()

    # Prepare the content for the API call
    content = PROMPT.format(schema=schema)
    messages = [
        {"type": "text", "text": content},
        *[
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": f"image/{file_container.image_type}",
                    "data": base64.b64encode(img).decode("utf-8"),
                },
            }
            for img in file_container.pages
        ],
    ]

    # Make the API call to Anthropic
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": messages,
                }
            ],
        )

        return response.content[0].text
    except Exception as e:
        print(f"An error occurred during Anthropic API call: {e}")
        return None


if __name__ == "__main__":
    main()
