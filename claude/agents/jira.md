---
name: jira
description: "Use this agent when the user wants help working from a Jira ticket/spec: clarify requirements, derive an implementation plan, and keep changes aligned with the ticket. The document below is the current spec context."
model: opus
---
<!-- Imported from ~/.claude/agents/jira.md -->

# Fat Static Library - Specification Driven Development

**Document Version**: 1.0
**JIRA Issue**: ES2-1469
**Author**: License Manager Team
**Last Updated**: 2025-01-24

---

## 1. Overview

### 1.1 Purpose

`liblicense.a` is a self-contained static library that bundles license-manager and all its dependencies (pqctoolkit-library/liboqs) into a single archive file.

### 1.2 Scope

> **Note**: This is an **additional** build option, not a replacement. The existing modular build (separate libraries + pkg-config for liboqs) remains unchanged and fully supported.

### 1.3 Build Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Modular** | Separate libraries + external liboqs | Development, testing, custom builds |
| **Fat static** | Single liblicense.a with all deps | CI/CD, Docker images, distribution |

---

## 2. Goals

1. **Single file distribution**: Use license functionality with just liblicense.a
2. **Faster CI builds**: Eliminate repeated pqctoolkit-library builds in CI
3. **Simplified dependencies**: No external liboqs installation required
4. **Backward compatibility**: Existing modular build remains unchanged

---

## 3. Architecture

### 3.1 Library Structure

```
liblicense.a (fat static library)
├── license_manager objects   (license.c, keystore.c, random_utils.c)
├── jwt_impl objects          (jwt.c)
├── crypto_backend objects    (crypto_backend.c, crypto_haetae.c, crypto_mldsa.c)
└── liboqs objects            (ML-KEM, ML-DSA, HAETAE, Smaug algorithms)
```

### 3.2 Dependency Chain (Before)

```
evi
└── evi-crypto (CPM)
    └── license_manager (CPM)
        └── liboqs (pkg-config/find_library)  ← external dependency
```

### 3.3 Dependency Chain (After)

```
evi
└── evi-crypto (CPM)
    └── liblicense.a (pre-built)  ← all dependencies included
```

### 3.3 Algorithms Included

| Category | Algorithms |
|----------|------------|
| **Signatures** | HAETAE-2, HAETAE-3, HAETAE-5, ML-DSA-44, ML-DSA-65, ML-DSA-87 |
| **KEM** | ML-KEM-512, ML-KEM-768, ML-KEM-1024, Smaug-1, Smaug-3, Smaug-5 |

---

## 4. Build Process

### 4.1 Step 1: Build pqctoolkit-library

```bash
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=OFF \
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
    -DOQS_ENABLE_SIG_HAETAE=ON \
    -DOQS_ENABLE_SIG_ML_DSA=ON \
    -DOQS_ENABLE_KEM_ML_KEM=ON \
    -DOQS_ENABLE_KEM_SMAUG=ON \
    -DOQS_MINIMAL_BUILD="KEM_ml_kem_512;KEM_ml_kem_768;..."
```

Output: `liboqs.a`

### 4.2 Step 2: Build license-manager

```bash
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
    -DBUILD_LICENSE_CLI=OFF \
    -DBUILD_LICENSE_TESTS=OFF
```

Output:
- `liblicense_manager.a`
- `libjwt_impl.a`
- `libcrypto_backend.a`

### 4.3 Step 3: Merge Libraries (MRI Script)

Using GNU ar MRI script to properly merge archives without object file name collisions:

```bash
cat > merge.mri << EOF
create liblicense.a
addlib liboqs.a
addlib liblicense_manager.a
addlib libjwt_impl.a
addlib libcrypto_backend.a
save
end
EOF

ar -M < merge.mri
ranlib liblicense.a
```

> **Note**: Direct `ar -x` extraction causes object file name collisions (e.g., multiple `poly.c.o` files from different algorithms). The MRI script approach preserves all objects.

---

## 5. Output Structure

```
dist/
├── linux-x86_64/
│   ├── liblicense.a      (~1.6 MB, ~4300 symbols)
│   └── include/
│       ├── license.h
│       ├── jwt.h
│       ├── crypto_backend.h
│       ├── random_utils.h
│       └── oqs/
│           ├── oqs.h
│           ├── sig_haetae.h
│           ├── sig_ml_dsa.h
│           ├── kem_ml_kem.h
│           ├── kem_smaug.h
│           └── ...
├── linux-aarch64/
│   └── ...
└── darwin-arm64/
    └── ...
```

---

## 6. Testing

### 6.1 Test File

Location: `tests/test_fat_static.c`

### 6.2 Test Cases

| Test | Description |
|------|-------------|
| `test_crypto_backend_init` | Verify crypto_get_backend() returns valid ML-DSA-87 backend |
| `test_license_key_sizes` | Verify license_get_key_sizes_for_level() returns correct sizes for ML-DSA-87 |
| `test_license_keypair_generation` | Generate ML-DSA-87 keypair and verify non-zero keys |
| `test_jwt_base64url` | Test JWT base64url encode/decode round-trip |
| `test_oqs_symbols` | Verify OQS_init() is callable (symbol linked) |
| `test_haetae_backend` | Verify HAETAE-5 backend availability |

### 6.3 Running Tests

Tests run automatically as part of the build script:

```bash
./scripts/build-fat-static.sh
```

Or manually:

```bash
gcc -o test_fat_static tests/test_fat_static.c \
    -Idist/linux-x86_64/include \
    -Wl,--whole-archive dist/linux-x86_64/liblicense.a -Wl,--no-whole-archive \
    -lssl -lcrypto -lpthread -ldl

./test_fat_static
```

### 6.4 Expected Output

```
===========================================
  Fat Static Library Test (liblicense.a)
===========================================

=== Test: crypto_get_backend ===
PASS: crypto_get_backend(ML-DSA, 87) returns non-NULL
PASS: backend->get_algorithm_name() returns non-NULL
  Algorithm: ML-DSA-87

=== Test: license_get_key_sizes_for_level ===
PASS: license_get_key_sizes_for_level succeeds
...

===========================================
  All tests PASSED!
===========================================
```

---

## 7. CI Integration

### 7.1 Workflow File

Location: `.github/workflows/build-fat-static.yml`

### 7.2 Build Matrix

| Runner | Architecture |
|--------|--------------|
| `ubuntu-24.04` | linux-x86_64 |
| `ubuntu-24.04-arm` | linux-aarch64 |

### 7.3 Triggers

- Push to `main` or `ES2-*` branches (with path filters)
- Pull requests to `main` (with path filters)
- Manual trigger (`workflow_dispatch`)

### 7.4 Artifacts

| Artifact | Contents | Retention |
|----------|----------|-----------|
| `liblicense-{arch}` | liblicense.a + headers | 30 days |
| `liblicense-release` | tar.gz archives for all archs | 90 days (main only) |

### 7.5 Integration with evi CI

```yaml
# In evi/.github/workflows/pr.yml
- name: Download liblicense
  uses: actions/download-artifact@v4
  with:
    name: liblicense-linux-x86_64
    path: deps/license

- name: Build with liblicense
  run: |
    cmake -DLICENSE_LIB_DIR=$PWD/deps/license ...
```

---

## 8. Usage in Downstream Projects

### 8.1 CMakeLists.txt Integration

```cmake
# Use pre-built liblicense.a
set(LICENSE_LIB_DIR "${CMAKE_CURRENT_SOURCE_DIR}/lib/${ARCH}")
add_library(license STATIC IMPORTED)
set_target_properties(license PROPERTIES
    IMPORTED_LOCATION "${LICENSE_LIB_DIR}/liblicense.a"
    INTERFACE_INCLUDE_DIRECTORIES "${LICENSE_LIB_DIR}/include"
)

target_link_libraries(your_target PRIVATE license)
```

### 8.2 Link Dependencies

Additional system libraries required when using liblicense.a:

| Platform | Libraries |
|----------|-----------|
| Linux | `-lssl -lcrypto -lpthread -ldl` |
| macOS | `-framework Security -lpthread` |

### 8.3 Docker Image Integration

```dockerfile
# Copy pre-built liblicense.a
COPY dist/linux-x86_64/liblicense.a /opt/license/lib/
COPY dist/linux-x86_64/include/ /opt/license/include/

ENV LICENSE_LIB_DIR=/opt/license
```

---

## 9. Build Script

### 9.1 Usage

```bash
./scripts/build-fat-static.sh [--arch <arch>] [--output-dir <dir>]
```

### 9.2 Options

| Option | Description | Default |
|--------|-------------|---------|
| `--arch` | Target architecture | Auto-detect |
| `--output-dir` | Output directory | `./dist` |

### 9.3 Supported Architectures

- `linux-x86_64`
- `linux-aarch64`
- `darwin-arm64`
- `darwin-x86_64`

---

## 10. Size Comparison

| Component | Size |
|-----------|------|
| liboqs.a (minimal build) | ~1.5 MB |
| liblicense_manager.a | ~47 KB |
| libjwt_impl.a | ~15 KB |
| libcrypto_backend.a | ~28 KB |
| **liblicense.a (merged)** | **~1.6 MB** |
| Symbols count | ~4,300 |

---

## 11. Security Considerations

1. **No secrets in binary**: liblicense.a contains no keys or tokens
2. **Reproducible builds**: Same source produces same binary
3. **Version tracking**: Record pqctoolkit-library version used in build
4. **Position-independent code**: Built with `-fPIC` for shared library compatibility

---

## 12. Migration Plan

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Add build script to license-manager repo | ✅ Complete |
| 2 | Add tests for fat static library | ✅ Complete |
| 3 | Add CI workflow | ✅ Complete |
| 4 | Update evi-crypto to use liblicense.a | Pending |
| 5 | Include pre-built liblicense.a in Dockerfile.env | Pending |
| 6 | Remove pqctoolkit-library build from evi CI | Pending |

---

## 13. Related Files

| File | Description |
|------|-------------|
| `scripts/build-fat-static.sh` | Fat library build script |
| `tests/test_fat_static.c` | Test suite for fat static library |
| `.github/workflows/build-fat-static.yml` | CI build workflow |
| `CMakeLists.txt` | license-manager build configuration |
| `docs/fat-static-library.md` | This document |

---

## Appendix A: Troubleshooting

### A.1 Undefined Symbol Errors

If you see undefined symbol errors when linking:

```
undefined reference to `pqcrystals_ml_dsa_65_ref_keypair'
```

**Cause**: Object files were lost during archive merge due to name collisions.

**Solution**: Ensure the build script uses MRI script approach, not direct `ar -x` extraction.

### A.2 OpenSSL Not Found

```
fatal error: openssl/evp.h: No such file or directory
```

**Solution**: Install OpenSSL development headers:
```bash
# Ubuntu/Debian
sudo apt-get install libssl-dev

# macOS
brew install openssl
export OPENSSL_ROOT_DIR=$(brew --prefix openssl)
```

### A.3 Test Compilation Fails

**Solution**: Use `--whole-archive` flag:
```bash
gcc -Wl,--whole-archive liblicense.a -Wl,--no-whole-archive ...
```
