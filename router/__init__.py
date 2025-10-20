import math
from pydantic import BaseModel


class Pagination(BaseModel):
    size: int = 0
    totalElements: int = 0
    totalPages: int = 0

    @staticmethod
    def count_total_pages(size, count):
        return Pagination(size=size,
                          totalElements=count,
                          totalPages=math.ceil(count / size) if count else 0)
        
def router_param_builder(tag):
    result = {
        "prefix": f"/{tag.replace('_', '/').replace('-', '_')}",
        "tags": [tag.replace("_", " ")],
    }
    return result