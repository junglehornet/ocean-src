# math

Binary64 (`float`) mathematics implemented in Ocean and inline assembly, with
no C extern functions or calls to libm.

```oc
package main;
import "math";

func main() {
    root: float = math.Pow(9.0, 0.5);
    wave := math.Sin(math.Pi / 6.0); // angles are radians
}
```

| Group | Exports |
| --- | --- |
| Constants | `Pi`, `E`, `Ln2`, `Sqrt2` |
| Trigonometry | `Sin`, `Cos`, `Tan`, `Asin`, `Acos`, `Atan`, `Atan2(y, x)` |
| Powers and logarithms | `Pow(x, y)`, `Exp`, `Exp2`, `Log` (natural), `Log2`, `Log10`, `Sqrt`, `Hypot(x, y)` |
| Rounding and arithmetic | `Abs`, `Copysign`, `Trunc`, `Floor`, `Ceil`, `Round`, `Min`, `Max`, `Mod` |
| IEEE helpers | `NaN()`, `Inf(sign int)`, `IsNaN`, `IsInf(x, sign int)`, `Signbit`, `Float64bits`, `Float64frombits` |

Mathematical inputs and outputs are `float`, including **`Pow(x float, y float)
float`**. Classification functions return `bool`; bit conversion uses `uint`.
`Inf` returns negative infinity for a negative sign and positive infinity otherwise.
`IsInf` accepts either infinity when sign is zero, and the specified sign otherwise.
Constants are ordinary exported bindings; treat them as read-only by convention.

`Round` rounds ties away from zero. `Mod` uses a quotient truncated toward zero
and preserves the dividend's sign, including signed zero. `Min` and `Max`
propagate NaN and select negative and positive zero respectively.

Domain errors return NaN. `Log(0)` returns negative infinity; overflow returns
infinity and underflow produces subnormal values or signed zero. `Pow` handles
negative bases with integral exponents, signed zeros, infinities, and the
identities `Pow(NaN(), 0) == 1` and `Pow(1, NaN()) == 1`.

Integer powers use exponentiation by squaring. On x86-64, fractional powers use
x87 `fyl2x`, `f2xm1`, and `fscale`, retaining extended precision until the result
is stored. Other architectures use Ocean logarithm/exponential routines.
`Sqrt` uses baseline native instructions on x86-64, AArch64, and RISC-V64;
other targets use a normalized Newton iteration. Remaining algorithms use
portable Ocean arithmetic and IEEE bit decomposition. No optional x86 SIMD
extensions are required.

These routines are approximations, not guaranteed correctly rounded libm
replacements. Trigonometric reduction uses a binary64 approximation of 2π;
angle error grows with input magnitude, and very large angles can lose all
meaningful phase information. `Tan` also loses accuracy near its poles.
For accurate trigonometry, keep inputs close to a few revolutions. The portable
`Pow` fallback can amplify logarithm rounding for large exponents.
Native paths have been executed on x86-64; other architecture paths require
validation on their respective hosts.

Run the Ocean unit tests (stored directly in this directory):

```sh
OCEAN_SRC="$PWD" ocean test math --notty
```
