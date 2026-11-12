# reflect

`reflect` exposes independently owned snapshots of struct fields and active enum payloads.

```ocean
import "reflect";

struct Person { name string; age int; }

// Returns fields in declaration order, including private fields.
fields := reflect.Fields(Person{"Ada", 36});
// fields[0].Name == "name"
// fields[0].Value.(string) == "Ada"
```

The public API is:

- `struct Field { Name string; Value any; }`
- `Fields(value any) array<Field>` returns all fields in declaration order,
  including struct value parameters. Other values return an empty array.
- `IsStruct(value any) bool` identifies struct values, including empty structs
  and instantiated generic or named struct types.

Names and values are independent copies. Updating a snapshot or the original
value cannot mutate the other. Strings, arrays, dynamic arrays, nested structs,
and boxed values follow normal deep-copy and scope-cleanup rules. Pointer
fields are non-owning copies of their addresses. Reflection does not follow
pointers: use `Fields(*pointer)` explicitly when its pointee is valid.

Compiler-only primitives implement these operations. The loader grants access
only to the actual `reflect` package under the configured standard-library
root, normally `<install directory>/src/reflect`. A copied source file, a
project-local package named `reflect`, and symlinks escaping that directory do
not receive access. Importing the public `reflect` API is supported in ordinary
Ocean code; calling its compiler primitives directly is rejected.

`reflect.IsEnum(value any)` identifies enum values, including generic enums,
`Optional<T>`, and `Result<T>`. `reflect.EnumVariant(value any)` returns the
qualified declaration name such as `Event.Key` (without generic arguments), or
an empty string for a non-enum. Pointers are not dereferenced.
`reflect.Fields` also snapshots the active enum payload: record fields keep
their names, tuple entries have empty names, fixed payloads return one unnamed
field, and unit variants return no fields. The same deep-copy rules apply.
`reflect.IsStruct` returns false for enum values.

`io.Print`, `io.Println`, `io.Sprint`, and formatted output use this reflection
to print enums recursively: `Event.Load`, `Event.Key(65)`, and
`Event.Click(x: 2, y: 3)`. Fixed payloads print as `Number.One(1)`.
