from typing import Annotated, TypeAlias

from pydantic import BaseModel, EmailStr, Field, HttpUrl, ValidationError, conlist


class Book(BaseModel):
    title: str
    author: str
    pages: int = Field(gt=10)


NonEmptyBooks: TypeAlias = conlist(Book, min_length=1)  # pyright: ignore[reportInvalidTypeForm]


class BookList(BaseModel):
    books: NonEmptyBooks


# try:
#     valid_book_list = BookList(
#         books=[
#             Book(title="Dune", author="Frank Herbert", pages=412),
#             Book(title="Clean Code", author="Robert C. Martin", pages=464),
#         ]
#     )
#     print("Valid:", valid_book_list)
# except ValidationError as error:
#     print("Validation failed:", error)

# try:
#     empty_book_list = BookList(books=[])
#     print("Empty list:", empty_book_list)
# except ValidationError as error:
#     print("Empty list rejected:", error)

# try:
#     invalid_page_count = BookList(
#         books=[{"title": "Short Book", "author": "Example Author", "pages": 10}]
#     )
#     print("Invalid pages:", invalid_page_count)
# except ValidationError as error:
#     print("Invalid pages rejected:", error)

###################################################################################

class Student(BaseModel):
    name: str
    email: EmailStr
    portfolio: HttpUrl
    skills: conlist(str, min_length=2, max_length=5)  # pyright: ignore[reportInvalidTypeForm]


######################################################################################

class Product(BaseModel):
    name: str = Field(..., min_length=2)
    price: float = Field(..., gt=0)


try:
    product = Product(name="", price=-20)
except ValidationError as e:
    print(e.json(indent=2))
