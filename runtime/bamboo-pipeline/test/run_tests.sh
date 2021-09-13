

if [[ ! -d "./bamboo_engine" ]]
    cp -r ../../../bamboo_engine/ .
fi

if [[ ! -d "./pipeline" ]]
    cp -r ../pipeline .
fi

python manage.py migrate

python manage.py celery worker -c 8 &

pytest pipeline_test_use/tests
