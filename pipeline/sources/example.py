import dlt


@dlt.resource(name="connection_check", write_disposition="replace")
def connection_check():
    yield {"id": 1, "status": "ok"}


def run() -> None:
    pipeline = dlt.pipeline(
        pipeline_name="case_law",
        destination="postgres",
        dataset_name="raw",
    )
    print(pipeline.run(connection_check()))


if __name__ == "__main__":
    run()
