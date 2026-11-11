# mem

`Copy(src *void, dest *void, bytes int)` copies exactly `bytes` bytes from
source to destination. Overlapping regions are supported in either direction.
It returns no value and does not allocate memory.

Both regions must be valid for the requested byte count; destination storage
must be writable. A zero count accesses neither pointer and permits null
pointers. Negative counts panic.

```oc
import "mem";

// Shift the first three bytes one position to the right.
data: u8[4] = {1, 2, 3, 4};
mem.Copy(&data[0], &data[1], 3); // data is now {1, 1, 2, 3}
```

Copy operates on raw bytes and does not copy ownership or adjust references.
Use ordinary Ocean assignment to copy values containing owned data.

Run tests with `ocean test mem`.
