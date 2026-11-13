# encoding/json

A small Go-inspired JSON package. Recoverable failures use Ocean `Result<T>`.

```ocean
import "encoding/json";

struct Person { Name string; Age int; }
encoded := json.Marshal(Person{"Ada", 36}).unwrap();
value := json.Unmarshal(encoded).unwrap();
object := value.(map[string]any);
age := object["Age"].(json.Number).Int64().unwrap();
```

- `Marshal(value any) Result<string>` encodes null, booleans, strings, all integer
  widths, finite floats, structs, `map[string]any`, `mixed any[]`, and dynamic
  `string[]`, `int[]`, `float[]`, and `bool[]` arrays. Object keys are sorted.
- `Unmarshal(text string) Result<any>` decodes to null, bool, string, `Number`,
  `mixed any[]`, or `map[string]any`. Duplicate object keys retain the last value.
- `Valid(text string) bool` checks an entire JSON document.
- `Number { Text string }` preserves the original JSON number, including large
  integers and exponents. `Int64() Result<int>` and `Float64() Result<float>`
  convert it with range checking. Marshal validates Number before emitting it.

Strings require valid UTF-8. Escapes, including UTF-16 surrogate pairs, are
validated; isolated surrogates are errors. NaN and infinities are rejected.
Nesting is limited to 128 levels. Unsupported types return errors.

Differences from Go: input and output are strings; Unmarshal returns a dynamic
value rather than assigning through a pointer. Numbers always use Number rather
than float64. Struct encoding includes all declared fields, including private
fields, under their exact names; tags and custom marshalers are not implemented.
Fixed arrays, pointers, concrete maps such as `map[string]int`, streaming
encoders/decoders, indentation, and struct decoding are not implemented.

Requires the compiler's interface-array mutation, enum tuple boxing, and boxed
array ownership fixes. Run `ocean test encoding/json` with the matching compiler
and `OCEAN_SRC` pointing to this tree.
