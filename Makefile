.PHONY: install app test sample

install:
	python -m pip install -r requirements.txt

app:
	streamlit run app/streamlit_app.py

test:
	pytest

sample:
	python scripts/generate_sample_assets.py

