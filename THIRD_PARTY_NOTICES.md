# Third-party components

Mika uses the following independently licensed components. Original license texts
and notices are retained under [`licenses/`](licenses/). Mika's original code is
[MIT-licensed](LICENSE); third-party components retain their own licenses.

| Component | Pinned source | License |
| --- | --- | --- |
| transcribe.cpp | [b61b7f936e4e728f8999a8c3e98c7112e700410e](https://github.com/handy-computer/transcribe.cpp/tree/b61b7f936e4e728f8999a8c3e98c7112e700410e) | MIT |
| ggml and bundled inference components | Vendored by the pinned transcribe.cpp archive | MIT and notices listed below |
| miniaudio | [9634bedb5b5a2ca38c1ee7108a9358a4e233f14d](https://github.com/mackron/miniaudio/tree/9634bedb5b5a2ca38c1ee7108a9358a4e233f14d) | Public domain or MIT-0, at the recipient's choice |
| Granite Speech 5.0 470M TurboCTC Q4_K_M | [GGUF revision 0cf5be9f4bcd479989e6a24d142094d34d552daa](https://huggingface.co/handy-computer/granite-speech-5.0-470m-turboctc-gguf/tree/0cf5be9f4bcd479989e6a24d142094d34d552daa) | Apache-2.0 |

The Granite model is derived from
[`ibm-granite/granite-speech-5.0-470m-turboctc`](https://huggingface.co/ibm-granite/granite-speech-5.0-470m-turboctc).
Mika uses the standard Apache-2.0 weights, **not** the separately licensed
non-commercial `-nc` weights. Model files are downloaded separately at runtime,
with user consent; the exact expected payload checksum is in `src/model.h`.

Included documents:

- `licenses/transcribe.cpp-LICENSE.txt`
- `licenses/transcribe.cpp-THIRD-PARTY-LICENSES.md` (upstream bundled component notices)
- `licenses/ggml-LICENSE.txt`
- `licenses/miniaudio-LICENSE.txt`
- `licenses/granite-speech-LICENSE.txt`
- `licenses/granite-speech-NOTICE.txt`

The following dependencies are not vendored in this source repository. Release
packages statically link curl, OpenSSL libcrypto, and zlib via the pinned vcpkg
manifest, and include their notices under `licenses/dependencies/`:

- [libcurl](https://curl.se/docs/copyright.html), curl license.
- [OpenSSL libcrypto](https://www.openssl.org/source/license.html), Apache-2.0 for
  OpenSSL 3.x; OpenSSL 1.1.1 uses its older OpenSSL/SSLeay terms.
- The selected compiler's C/C++ runtimes and operating-system audio libraries.

The **unreleased**, opt-in punctuation prototype additionally uses the English
[FullStop/truecase model](https://huggingface.co/1-800-BAD-CODE/punctuation_fullstop_truecase_english)
(Apache-2.0; modified by pinned INT8 conversion), native SentencePiece v0.2.1
(Apache-2.0 with bundled protobuf-lite/Abseil/Darts notices), and CPU ONNX Runtime
1.28.2 (MIT and third-party notices). Only the runtime is extracted from the
sherpa-onnx v1.13.8 SDK; no Sherpa inference library is deployed. The native bridge
and source-preserving renderer are original Mika code.
It is not part of ordinary builds/releases. The developer fetcher pins all assets
and retains their notices under the prototype's `punctuation/licenses/` directory,
including the model card and explicit modification notice. Python conversion
packages are developer tooling, not deployed runtime dependencies. See
[docs/punctuation.md](docs/punctuation.md) for provenance, source-availability
links, measurements, and limitations. No model/runtime is relicensed as Mika MIT.

Binary redistributors must preserve applicable dependency/model notices and comply
with the licenses of the actual linked or bundled versions. A native-optimized
build also has a machine-specific CPU instruction-set requirement; see README.
