def get_class_from_str(name: str, cls_dict: dict):
    if name not in cls_dict.keys():
        raise ValueError(f"Class '{name}' is not implemented.")
    return cls_dict[name]
