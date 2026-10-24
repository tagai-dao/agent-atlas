"""Stable contract identity for activity; display symbols are never unique IDs."""
LEGACY = [
    {'address':'0xfa81c13f979f0dff4a40b68c4aba147fa0723333','symbol':'AIPRO','name':'AIPRO','protocol':'tagai','decimals':18},
    {'address':'0x7ffcf7b3b52adcc00c76f50ce2e37bf3c7e215dc','symbol':'.ai','name':'Agentic Inu','protocol':'manual','decimals':18},
    {'address':'0x0c6302401aa5325c2e36f170f52c00b1d220b405','symbol':'GANG','name':'GANG','protocol':'gang','decimals':18},
    {'address':'0xb8fb293b3e8e3c5fd741e34ac5810dd5dc9f2c7f','symbol':'Flaip','name':'Flaip','protocol':'manual-curve','decimals':18},
]
ALIASES={a['symbol']:a['address'] for a in LEGACY}
ALIASES['dotai']=ALIASES['.ai']

def asset_address(row):
    return (row.get('assetId') or row.get('address') or row.get('token') or ALIASES.get(row.get('asset') or row.get('symbol')) or '').lower()
