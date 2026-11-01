# reflect

`reflect` exposes independently owned snapshots of struct fields.

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
  including struct value parameters. Non-struct values return an empty array.
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

`OCEAN_SRC` explicitly overrides the trusted standard-library root for compiler
development. It is compiler configuration, not a permission granted by source
code. Reflection reads field snapshots; it exposes no raw struct-layout access.
