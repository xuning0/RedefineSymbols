import re


def is_apple_symbol(name):
    """
    Determine if the prefix is ​​Apple's official namespace.

    Listed below are most of Apple's official namespaces. If the namespace used by your third-party library is in it,
    delete it from below.
    """
    return re.fullmatch('^(NS|UI|WK|AB|CX|CP|CLS|CN|CL|CS|CT|EK|HK|HM|AD|MK|MF|MC|NK|NC|PK|QL|SF|INUI|SK|UN|WC|AM|SB|'
                        'AR|CA|GK|GLK|MTK|PDF|IK|QC|RP|SCN|AV|MP|PH|VN|AS|CB|NFC|CT|CW|TK|EA|IMK|IO|OS)'
                        '[A-Z][A-Za-z]*', name) is not None
