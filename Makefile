release:
	rm -r dist
	. venv/bin/activate; python setup.py sdist bdist_wheel && twine upload dist/*
	rm -r dist

update:
	pip uninstall sanic-session; python setup.py install