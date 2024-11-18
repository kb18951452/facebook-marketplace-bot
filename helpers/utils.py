from itertools import product


def combine_multiple_dict_lists(*dict_lists):
    # Collect all keys from all dictionaries to ensure all are represented
    all_keys = set()
    for dict_list in dict_lists:
        for d in dict_list:
            all_keys.update(d.keys())

    result = []
    for i, combo in enumerate(product(*dict_lists), start=1):
        # Start with a dictionary of None for all keys
        combined = {key: None for key in all_keys}

        # Update with values from each dictionary in the current combination
        for d in combo:
            combined.update(d)

        # Add a unique identifier
        combined['listing_id'] = f"listing_{i}"
        result.append(combined)

    return result
