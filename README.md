# 📊⚡ impulse

`impulse` is a proof of concept showing how to prompt a Vision Language Model with Protobufs to do data extraction from an image.
The `client.py` file of this project exposes a CLI that allows the caller to pass an image (local or URL) and local Protobuf path to the server.
Using the image and the Protobuf, the server will call the model, get a response, then `Parse` the response into a Protobuf `message` of the same type specified by the caller.
The server then packs the Protobuf message into an Any and returns it to the caller, who again unpacks it into the target Protobuf `message`.
The client prints the resulting Protobuf, showing it contains the expected data and is of the expected type.

The magic happens when you modify the Protobuf.
Since the Protobuf message serves as both the data model in the application and part of the prompt instructions to the model, changing the Protobuf is all you need to do to extract additional data from the image using this approach.

## Try it out

This project uses [`direnv`](https://direnv.net/) to manage its environment.
If you use `direnv` copy `.envrc.template` and add the API keys for the services you intend to use.
All are optional, but OpenAI is used by default.

```sh
cp .envrc.template .envrc
```

If you don't want to use `direnv`, you will still need to add the environment variables using your preferred approach.

### Install dependencies and run codegen

```sh
make install protos
```

### Run the server

```sh
make serve
```

### Run the client

```sh
python -m impulse.client --file_path "<url/path>" --proto_schema "protos/.../<your_file>.proto:<message_name>"
```

For example

```sh
. .venv/bin/activate
python -m impulse.client --file_path "https://d85ecz8votkqa.cloudfront.net/support/help_center/Print_Payment_Receipt.JPG" --proto_schema "protos/receipt/receipt.proto:Receipt"
```

The output should look something like this

```text
Proto instance (<class 'receipt.receipt_pb2.Receipt'>):
id: "e6d598ef"
merchant_name: "Main Street Restaurant"
timestamp: 1491576960
total_amount: 29.01
items {
  name: "Sub Total"
  price: 25.23
  quantity: 1
}
items {
  name: "Tip"
  price: 3.78
  quantity: 1
}
```

### Augment the Protobuf message extraction schema

Open `protos/receipt/receipt.proto`


```proto
syntax = "proto3";

package receipt;

message Receipt {
  string id = 1;
  string merchant_name = 2;
  int64 timestamp = 3;
  double total_amount = 4;
  repeated Item items = 5;

  message Item {
    string name = 1;
    double price = 2;
    int32 quantity = 3;
  }
  string card_type = 6; // lower case
}
```

Regenerate the Protobuf code

```sh
make protos
```

Looking at the [receipt](https://d85ecz8votkqa.cloudfront.net/support/help_center/Print_Payment_Receipt.JPG) from our example above, we expect `card_type` to be `"discover"`, since we gave instructions in a comment to make the output lower case.

Now, let's run it

```sh
. .venv/bin/activate
python -m impulse.client --file_path "https://d85ecz8votkqa.cloudfront.net/support/help_center/Print_Payment_Receipt.JPG" --proto_schema "protos/receipt/receipt.proto:Receipt"
```

We see our newly added field with the expected value `"discover"`.

```text
Proto instance (<class 'receipt.receipt_pb2.Receipt'>):
id: "9hqjxvufdr"
merchant_name: "Main Street Restaurant"
timestamp: 1491561360
total_amount: 29.01
items {
  name: "Sub Total"
  price: 25.23
  quantity: 1
}
items {
  name: "Tip"
  price: 3.78
  quantity: 1
}
card_type: "discover"
```

Pretty magical.

Keep in mind, the `.proto` file is being sent as part of the prompt as context to the model.
If you're having trouble getting the output you want, try writing more descriptive comments in the Protobuf or give a few examples.
The following could have also given us the result we were looking for

```proto
syntax = "proto3";

package receipt;

message Receipt {
  string id = 1;
  string merchant_name = 2;
  int64 timestamp = 3;
  double total_amount = 4;
  repeated Item items = 5;

  message Item {
    string name = 1;
    double price = 2;
    int32 quantity = 3;
  }
  // lower case, e.g. "visa", "mastercard", etc.
  string card_type = 6;
}
```

## Critical analysis of the project by a model

> While intriguing for quick experiments, a critical engineer might find this more of a clever hack than a robust, production-ready solution. Its real-world applicability is limited without addressing performance, security, and scalability concerns.

Have fun!
