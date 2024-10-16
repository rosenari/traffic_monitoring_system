import os
import pytest
import tempfile
import pytest_asyncio
from app.database import get_redis
from fastapi import UploadFile
from app.services.file_service import FileService
from app.repositories.file_repository import FileRepository


@pytest_asyncio.fixture
async def redis():
    async for ri in get_redis('redis://localhost:6379/0'):
        yield ri


@pytest.fixture
def temp_directory():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def temp_file_in_directory(temp_directory):
    temp_file_path = os.path.join(temp_directory, "temp_test_file.txt")
    with open(temp_file_path, "wb") as temp_file:
        temp_file.write(b'test file')
    yield temp_file_path


@pytest.fixture
def file_service(temp_directory, redis) -> FileService:
    repository = FileRepository(file_directory=temp_directory)
    service = FileService(repository=repository, redis=redis)
    return service


@pytest.mark.asyncio
async def test_upload_file(file_service: FileService, temp_directory, temp_file_in_directory):
    file_content = b"this is a test file"
    with open(temp_file_in_directory, "wb") as temp_file:
        temp_file.write(file_content)

    with open(temp_file_in_directory, "rb") as temp_file_for_upload:
        upload_file = UploadFile(filename="temp_test_file.txt", file=temp_file_for_upload)

        await file_service.upload_file(upload_file)

    uploaded_file_path = os.path.join(temp_directory, "temp_test_file.txt")
    assert os.path.exists(uploaded_file_path)

    with open(uploaded_file_path, "rb") as f:
        saved_content = f.read()
    assert saved_content == file_content


def test_delete_file(file_service: FileService, temp_file_in_directory):
    print(temp_file_in_directory)
    assert os.path.exists(temp_file_in_directory)

    file_service.delete_file(os.path.basename(temp_file_in_directory))

    assert not os.path.exists(temp_file_in_directory)


def test_get_file_list(file_service: FileService, temp_directory):
    file_names = ["file1.txt", "file2.txt", "file3.txt"]
    for file_name in file_names:
        with open(os.path.join(temp_directory, file_name), "w") as f:
            f.write("test content")

    file_list = file_service.get_file_list()
    file_list = [file['file_name'] for file in file_list]

    assert sorted(file_list) == sorted(file_names)


@pytest.mark.asyncio
async def test_get_valid_file_list(file_service: FileService):
    ri = file_service.redis

    await ri.set('valid:file1', 'success')
    await ri.set('valid:file2', 'pending')

    result = await file_service.get_valid_file_list()

    assert {'file_name': 'file1', 'status': 'success'} in result
    assert {'file_name': 'file2', 'status': 'pending'} in result

    await ri.delete('valid:file1')
    await ri.delete('valid:file2')
    
    result_after_delete = await file_service.get_valid_file_list()
    assert {'file_name': 'file1', 'status': 'success'} not in result_after_delete
    assert {'file_name': 'file2', 'status': 'pending'} not in result_after_delete