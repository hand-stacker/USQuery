import http.request
import settings
def connect(s_link):
    resp, content = self.http.request(url, headers=settings.CONGRESS_KEY)
    content = u(content)
    content = json.loads(content)
    
    return content


