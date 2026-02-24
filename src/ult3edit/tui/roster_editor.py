"""TUI roster editor: form-based character list with field editing."""

from ..constants import (
    CHAR_RECORD_SIZE, CHAR_MAX_SLOTS,
    CHAR_READIED_WEAPON, CHAR_WORN_ARMOR,
    RACES, CLASSES,
)
from ..roster import Character
from .form_editor import FormField, FormEditorTab


def _character_label(char, index):
    """Generate display label for a character in the record list."""
    if char.is_empty:
        return f'[{index:2d}] (empty)'
    race = RACES.get(char.raw[0x16], '?')
    cls = CLASSES.get(char.raw[0x17], '?')
    return f'[{index:2d}] {char.name:<12s} {race:<6s} {cls:<10s} HP:{char.hp}'


def _character_fields(char):
    """Generate FormField list for editing a character."""
    fields = []

    fields.append(FormField('Name',
                             lambda: char.name,
                             lambda v: setattr(char, 'name', v)))
    from ..constants import RACE_CODES, CLASS_CODES, GENDERS, STATUS_CODES
    fields.append(FormField('Race',
                             lambda: char.race,
                             lambda v: setattr(char, 'race', v),
                             validator=lambda v: v.upper() in RACE_CODES))
    fields.append(FormField('Class',
                             lambda: char.char_class,
                             lambda v: setattr(char, 'char_class', v),
                             validator=lambda v: v.upper() in CLASS_CODES))
    fields.append(FormField('Gender',
                             lambda: char.gender,
                             lambda v: setattr(char, 'gender', v),
                             validator=lambda v: ord(v.upper()[0]) in GENDERS if v else False))
    fields.append(FormField('Status',
                             lambda: char.status,
                             lambda v: setattr(char, 'status', v),
                             validator=lambda v: ord(v.upper()[0]) in STATUS_CODES if v else False))
    fields.append(FormField('STR',
                             lambda: char.strength,
                             lambda v: setattr(char, 'strength', int(v)),
                             validator=lambda v: 0 <= int(v) <= 99,
                             fmt='int'))
    fields.append(FormField('DEX',
                             lambda: char.dexterity,
                             lambda v: setattr(char, 'dexterity', int(v)),
                             validator=lambda v: 0 <= int(v) <= 99,
                             fmt='int'))
    fields.append(FormField('INT',
                             lambda: char.intelligence,
                             lambda v: setattr(char, 'intelligence', int(v)),
                             validator=lambda v: 0 <= int(v) <= 99,
                             fmt='int'))
    fields.append(FormField('WIS',
                             lambda: char.wisdom,
                             lambda v: setattr(char, 'wisdom', int(v)),
                             validator=lambda v: 0 <= int(v) <= 99,
                             fmt='int'))
    fields.append(FormField('HP',
                             lambda: char.hp,
                             lambda v: setattr(char, 'hp', int(v)),
                             validator=lambda v: 0 <= int(v) <= 9999,
                             fmt='int'))
    fields.append(FormField('Max HP',
                             lambda: char.max_hp,
                             lambda v: setattr(char, 'max_hp', int(v)),
                             validator=lambda v: 0 <= int(v) <= 9999,
                             fmt='int'))
    fields.append(FormField('MP',
                             lambda: char.mp,
                             lambda v: setattr(char, 'mp', int(v)),
                             validator=lambda v: 0 <= int(v) <= 99,
                             fmt='int'))
    fields.append(FormField('EXP',
                             lambda: char.exp,
                             lambda v: setattr(char, 'exp', int(v)),
                             validator=lambda v: 0 <= int(v) <= 9999,
                             fmt='int'))
    fields.append(FormField('Gold',
                             lambda: char.gold,
                             lambda v: setattr(char, 'gold', int(v)),
                             validator=lambda v: 0 <= int(v) <= 9999,
                             fmt='int'))
    fields.append(FormField('Food',
                             lambda: f'{char.food_float:.2f}',
                             lambda v: setattr(char, 'food_float', float(v)),
                             validator=lambda v: 0 <= float(v) <= 9999.99,
                             fmt='float'))
    fields.append(FormField('Gems',
                             lambda: char.gems,
                             lambda v: setattr(char, 'gems', int(v)),
                             validator=lambda v: 0 <= int(v) <= 99,
                             fmt='int'))
    fields.append(FormField('Keys',
                             lambda: char.keys,
                             lambda v: setattr(char, 'keys', int(v)),
                             validator=lambda v: 0 <= int(v) <= 99,
                             fmt='int'))
    fields.append(FormField('Powders',
                             lambda: char.powders,
                             lambda v: setattr(char, 'powders', int(v)),
                             validator=lambda v: 0 <= int(v) <= 99,
                             fmt='int'))
    fields.append(FormField('Torches',
                             lambda: char.torches,
                             lambda v: setattr(char, 'torches', int(v)),
                             validator=lambda v: 0 <= int(v) <= 99,
                             fmt='int'))
    fields.append(FormField('In Party',
                             lambda: 'Yes' if char.in_party else 'No',
                             lambda v: setattr(char, 'in_party', v.lower() in ('yes', 'true', '1', 'y'))))
    fields.append(FormField('Marks',
                             lambda: ', '.join(char.marks) if char.marks else 'None',
                             lambda v: setattr(char, 'marks', [m.strip() for m in v.split(',')] if v.strip() and v.strip().lower() != 'none' else [])))
    fields.append(FormField('Cards',
                             lambda: ', '.join(char.cards) if char.cards else 'None',
                             lambda v: setattr(char, 'cards', [c.strip() for c in v.split(',')] if v.strip() and v.strip().lower() != 'none' else [])))
    fields.append(FormField('Weapon',
                             lambda: f'{char.raw[CHAR_READIED_WEAPON]} ({char.equipped_weapon})',
                             lambda v: setattr(char, 'equipped_weapon', int(v)),
                             fmt='int'))
    fields.append(FormField('Armor',
                             lambda: f'{char.raw[CHAR_WORN_ARMOR]} ({char.equipped_armor})',
                             lambda v: setattr(char, 'equipped_armor', int(v)),
                             fmt='int'))
    return fields


def make_roster_tab(data, save_callback, tab_name='Roster'):
    """Create a FormEditorTab for the character roster."""
    raw = bytearray(data)
    characters = []
    num_slots = len(raw) // CHAR_RECORD_SIZE
    for i in range(min(CHAR_MAX_SLOTS, num_slots)):
        offset = i * CHAR_RECORD_SIZE
        characters.append(Character(raw[offset:offset + CHAR_RECORD_SIZE]))

    def get_save_data():
        out = bytearray(len(raw))
        for i, ch in enumerate(characters):
            offset = i * CHAR_RECORD_SIZE
            out[offset:offset + CHAR_RECORD_SIZE] = ch.raw
        return bytes(out)

    return FormEditorTab(
        tab_name=tab_name,
        records=characters,
        record_label_fn=_character_label,
        field_factory=_character_fields,
        save_callback=save_callback,
        get_save_data=get_save_data,
    )
