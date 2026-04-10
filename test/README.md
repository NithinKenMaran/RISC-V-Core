# Testing Setup

First, clean existing build products

``` bash
make -f test_thing.mk clean
```

Then, run the test script

```bash
make -f test_smth.mk
```

## Example

```bash
make -f test_core.mk clean
make -f test_core.mk
```