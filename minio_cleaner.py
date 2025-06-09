from os import getenv

from minio import Minio

minio = Minio(
    endpoint="minio:9000",
    access_key=getenv("MINIO_ROOT_USER"),
    secret_key=getenv("MINIO_ROOT_PASSWORD"),
    secure=False,
)

def clean_all_avatars():
    for obj in minio.list_objects("avatars", recursive=True):
        minio.remove_object("avatars", obj.object_name)

def clean_all_messages():
    for obj in minio.list_objects("messages", recursive=True):
        minio.remove_object("messages", obj.object_name)

def clean_all_posts():
    for obj in minio.list_objects("posts", recursive=True):
        minio.remove_object("posts", obj.object_name)

if __name__ == '__main__':
    clean_all_avatars()
    clean_all_messages()
    clean_all_posts()