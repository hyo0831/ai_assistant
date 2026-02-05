import requests

REST_API_KEY = ""

url = "https://dapi.kakao.com/v2/local/search/category.json"

headers = {"Authorization": f"KakaoAK {REST_API_KEY}"}

params = {"category_group_code": "FD6", "x": "126.923654", "y": "37.556547", "radius": 1000, "size": 5}

response = requests.get(url, headers=headers, params=params)

print("status:", response.status_code)
print(response.json())
