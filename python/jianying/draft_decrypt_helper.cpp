#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>

int _ZN4lvve12EncryptUtils17decryptFileStreamEPKcS2_(const char* in, const char* out);

std::string _ZN4lvve12EncryptUtils7decryptERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEES9_Rb(
    const std::string& encrypted, const std::string& param, bool& ok);

static std::string read_file(const char* path) {
    std::ifstream in(path, std::ios::binary);
    std::ostringstream ss;
    ss << in.rdbuf();
    return ss.str();
}

static bool write_file(const char* path, const std::string& data) {
    std::ofstream out(path, std::ios::binary);
    if (!out) {
        return false;
    }
    out.write(data.data(), static_cast<std::streamsize>(data.size()));
    return static_cast<bool>(out);
}

int main(int argc, char** argv) {
    if (argc < 3) {
        std::fprintf(stderr, "usage: %s <input> <output>\n", argv[0]);
        return 2;
    }

    if (_ZN4lvve12EncryptUtils17decryptFileStreamEPKcS2_(argv[1], argv[2]) == 0) {
        return 0;
    }

    std::string encrypted = read_file(argv[1]);
    bool ok = false;
    std::string plain = _ZN4lvve12EncryptUtils7decryptERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEES9_Rb(
        encrypted, "{}", ok);
    if (!ok || plain.empty()) {
        return 1;
    }
    if (!write_file(argv[2], plain)) {
        return 1;
    }
    return 0;
}
