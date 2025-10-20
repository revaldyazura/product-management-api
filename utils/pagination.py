from typing import List, Dict

from pydantic import BaseModel

class Pagination:

    def get_paging(self, page: str, size: str) -> Dict[str, int]:
        result = {}
        page_int = int(page)
        limit = int(size)
        offset = limit * (page_int - 1)
        result["limit"] = limit
        result["offset"] = offset
        return result

    def get_pagination_info(self, total_data: str, data: List[dict], limit: str, page: str) -> Dict[str, str]:
        result = {}

        limit_double = float(limit)
        total_data_int = int(total_data)

        total_pages = int(-(-total_data_int // limit_double))

        result["size"] = limit
        result["totalElements"] = str(total_data_int)
        result["totalPages"] = str(total_pages)
        result["currentPage"] = page

        return result

class PaginationInfo(BaseModel):
    size: str
    totalElements: str
    totalPages: str
    currentPage: str