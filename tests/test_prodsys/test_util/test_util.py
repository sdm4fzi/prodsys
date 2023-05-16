import pytest

from prodsys.util import util

class Tets_get_class_from_str:
    
    def test_existing_key_returns_value(self,):
        working_example = {
            "class_1": "hello",
            "class_2": "bye"
        }
        result = util.get_class_from_str(name="class_1", cls_dict=working_example)
        assert result == "hello"

    def test_missing_key_raises_value_error(self,):
        working_example = {
            "class_1": "hello",
            "class_2": "bye"
        }
        with pytest.raises(ValueError):
            result = util.get_class_from_str(name="non_existing_key", cls_dict=working_example)


