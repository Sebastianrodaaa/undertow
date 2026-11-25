.PHONY: setup test play replay eval smoke train-d writer-e record weights

setup:
	python3 -m pip install --user torch --index-url https://download.pytorch.org/whl/cpu
	python3 -m pip install --user -r requirements.txt

weights:
	python3 -m undertow.weights

test:
	python3 test_undertow.py

play:
	python3 app/server.py --open

replay:
	python3 app/server.py --mode replay --open

smoke:
	python3 -m undertow.eval --cities paris --trials-per-city 1 --edit-count 3 --out results/smoke_core.json

eval:
	python3 -m undertow.eval --trials-per-city 5 --edit-count 4 --out results/core_arms.json

train-d:
	python3 -m undertow.train_gd --seconds 60 --size 32 --trials 2 --out results/arm_d_gradient.json

writer-e:
	python3 -m undertow.writer_local --attempts 1 --rounds 1 --out results/arm_e_writer.json

record:
	python3 scripts/record_demo.py
