import unittest

from album_selection import (
    AlbumSelectionError,
    album_selection_available,
    choose_album_cover_state,
    mark_album_submitted,
    normalise_album_selection,
    public_album_selection,
    reopen_album_selection,
    set_album_mode,
    toggle_album_photo,
)


class AlbumSelectionRuleTests(unittest.TestCase):
    def gallery(self, state=None):
        return {"id": "gallery-1", "album_selection": state or {}}

    def share(self, **overrides):
        return {
            "subfolder": None,
            "guest_upload_mode": False,
            "access_level": "download",
            **overrides,
        }

    def test_legacy_gallery_is_safely_off(self):
        state = normalise_album_selection({"id": "legacy"})
        self.assertEqual(state["mode"], "off")
        self.assertEqual(state["limit"], 40)
        self.assertEqual(state["selected_file_ids"], [])

    def test_enabling_defaults_to_40_and_off_preserves_choices(self):
        enabled = set_album_mode(self.gallery(), "40", at="2026-01-01T00:00:00+00:00")
        enabled["selected_file_ids"] = ["a", "b"]
        disabled = set_album_mode(self.gallery(enabled), "off")
        self.assertEqual(disabled["selected_file_ids"], ["a", "b"])
        reenabled = set_album_mode(self.gallery(disabled), "40")
        self.assertEqual(reenabled["selected_file_ids"], ["a", "b"])

    def test_40_to_60_preserves_choices(self):
        state = set_album_mode(self.gallery(), "40")
        state["selected_file_ids"] = ["a", "b"]
        upgraded = set_album_mode(self.gallery(state), "60")
        self.assertEqual(upgraded["limit"], 60)
        self.assertEqual(upgraded["selected_file_ids"], ["a", "b"])

    def test_changing_a_completed_plan_reopens_without_losing_choices(self):
        state = set_album_mode(self.gallery(), "40")
        state["selected_file_ids"] = [str(i) for i in range(40)]
        state = choose_album_cover_state(self.gallery(state), "cover-id", "cover.jpg")
        state = mark_album_submitted(self.gallery(state))
        upgraded = set_album_mode(self.gallery(state), "60")
        self.assertFalse(upgraded["locked"])
        self.assertEqual(len(upgraded["selected_file_ids"]), 40)
        self.assertEqual(upgraded["cover_file_id"], "cover-id")
        self.assertEqual(upgraded["history"][-2]["action"], "reopened_for_plan_change")

    def test_60_to_40_never_discards_excess_choices(self):
        state = set_album_mode(self.gallery(), "60")
        state["selected_file_ids"] = [str(i) for i in range(41)]
        with self.assertRaisesRegex(AlbumSelectionError, "already selected 41"):
            set_album_mode(self.gallery(state), "40")
        self.assertEqual(len(state["selected_file_ids"]), 41)

    def test_selection_limit_is_enforced(self):
        state = set_album_mode(self.gallery(), "40")
        state["selected_file_ids"] = [str(i) for i in range(40)]
        with self.assertRaisesRegex(AlbumSelectionError, "selected all 40"):
            toggle_album_photo(self.gallery(state), "extra")
        updated, selected = toggle_album_photo(self.gallery(state), "0")
        self.assertFalse(selected)
        self.assertEqual(len(updated["selected_file_ids"]), 39)

    def test_submit_requires_exact_count_and_separate_cover(self):
        state = set_album_mode(self.gallery(), "40")
        state["selected_file_ids"] = [str(i) for i in range(40)]
        with self.assertRaisesRegex(AlbumSelectionError, "separate cover"):
            mark_album_submitted(self.gallery(state))
        with_cover = choose_album_cover_state(self.gallery(state), "cover-id", "IMG_9999.jpg")
        submitted = mark_album_submitted(self.gallery(with_cover), at="2026-01-02T00:00:00+00:00")
        self.assertTrue(submitted["locked"])
        self.assertEqual(submitted["revision"], 1)
        self.assertEqual(submitted["cover_file_id"], "cover-id")

    def test_locked_selection_cannot_change_until_admin_reopens_it(self):
        state = set_album_mode(self.gallery(), "40")
        state["selected_file_ids"] = [str(i) for i in range(40)]
        state = choose_album_cover_state(self.gallery(state), "cover-id", "cover.jpg")
        state = mark_album_submitted(self.gallery(state))
        with self.assertRaisesRegex(AlbumSelectionError, "locked"):
            toggle_album_photo(self.gallery(state), "0")
        reopened = reopen_album_selection(self.gallery(state))
        self.assertFalse(reopened["locked"])
        self.assertEqual(len(reopened["selected_file_ids"]), 40)
        self.assertEqual(reopened["cover_file_id"], "cover-id")

    def test_album_controls_only_reach_primary_couple_share(self):
        gallery = self.gallery(set_album_mode(self.gallery(), "40"))
        self.assertTrue(album_selection_available(gallery, self.share()))
        self.assertFalse(album_selection_available(gallery, self.share(subfolder="Wedding Images")))
        self.assertFalse(album_selection_available(gallery, self.share(guest_upload_mode=True)))
        self.assertFalse(album_selection_available(gallery, self.share(access_level="view")))
        self.assertEqual(public_album_selection(self.gallery(), self.share()), {"enabled": False})


if __name__ == "__main__":
    unittest.main()
