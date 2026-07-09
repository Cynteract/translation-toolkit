# translation-toolkit

Shared localization dataset models and translation engine for internal
Python services that need multi-locale content management.

## Install

    pip install git+https://github.com/aditya-1967/translation-toolkit.git

## Usage

    from translation_toolkit import LocalizationDataset, Translator

    dataset = LocalizationDataset()
    dataset.add_entry("greetings", "hello_id", "en", "Hello")

    translator = Translator(service_account_path="path/to/service-account-key.json")
    translator.auto_translate(dataset, target_locales=["fr", "de", "es"])

    print(dataset.get_value("greetings", "hello_id", "fr"))