from curl_cffi import requests as r

x = r.get("https://www.arcelik.com.tr/mini-buzdolabi", impersonate="chrome")
print(x.status_code, x.text.count("prd-inner"), x.text.count("prc-last"))
