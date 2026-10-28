"""Static integration guards that can run without the GUI dependencies."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class IntegrationStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.features = (ROOT / 'feature_windows.py').read_text(encoding='utf-8')
        cls.learning = (ROOT / 'learning_content.py').read_text(encoding='utf-8')
        cls.spec = (ROOT / 'QRYVANTA.spec').read_text(encoding='utf-8')
        cls.iss = (ROOT / 'QRYVANTA-Setup.iss').read_text(encoding='utf-8')
        cls.readme = (ROOT / 'README.txt').read_text(encoding='utf-8')

    def test_help_menu_has_all_working_routes(self):
        for label, handler in (
            ('LEARN', 'show_learn'), ('HELP', 'show_help'), ('QUIZ', 'show_quiz'),
            ('COMPETITIVE EXAM', 'show_competitive_exam'), ('DEVELOPED BY', 'show_developed_by'),
        ):
            self.assertIn(f'("{label}", self.{handler})', self.app)
            self.assertIn(f'def {handler}(self):', self.app)
        header = self.app[self.app.find('header.addWidget(\n            self.logout_button'):self.app.find('main_layout.addLayout(header)')]
        self.assertLess(header.find('self.logout_button'), header.find('self.help_menu_button'))
        self.assertLess(header.find('self.help_menu_button'), header.find('self.theme_selector'))

    def test_five_theme_labels_and_day_night_palette_path_exist(self):
        for theme in ('NEO-BRUTALISM', 'CYBERCORE', 'SWISS', 'BENTO GRID', 'CYBERPUNK'):
            self.assertIn(theme, self.app)
        self.assertIn('def theme_variant(', self.app)
        self.assertIn('def toggle_day_night(self):', self.app)
        self.assertIn('APP_SETTINGS.setValue("night_mode", self.is_night_mode)', self.app)
        self.assertIn('self.analysis_panel.apply_theme(', self.app)
        self.assertIn('self.database_view.setStyleSheet(', self.app)

    def test_download_routes_are_connected_to_existing_data(self):
        for action in ('database_csv', 'history_txt', 'report_pdf', 'report_docx', 'report_txt'):
            self.assertIn(action, self.app)
        self.assertIn('export_table_csv(path, headers, rows)', self.app)
        self.assertIn('format_command_history(self.sqlplus_panel.history)', self.app)
        self.assertIn('self.analysis_panel.download_requested.connect(self.handle_download_action)', self.app)
        self.assertIn('def build_processing_report(report):', (ROOT / 'export_utils.py').read_text(encoding='utf-8'))

    def test_offline_media_fallbacks_and_people_details(self):
        self.assertRegex(self.features, r'FACULTY_NAME = "Dr\. Swaminathan A"')
        self.assertRegex(self.features, r'FACULTY_LABEL = "DBMS"')
        self.assertIn('FACULTY_PHOTO = "assets/fac.jpg"', self.features)
        self.assertIn('faculty_name_label = QLabel(FACULTY_NAME)', self.features)
        self.assertIn('faculty_department_label = QLabel(FACULTY_LABEL)', self.features)
        self.assertIn('("25BCE1914", "25BCE5327")', self.features)
        self.assertIn('Registration No.: {registration_number}', self.features)
        self.assertIn('("Sabyasaachi Pradhan", "Subhashish Roy")', self.features)
        for asset in ('assets/learn.mp4', 'assets/Dev1.jpg', 'assets/Dev2.jpg', 'assets/fac.jpg'):
            self.assertIn(asset, self.features)
        self.assertIn('text course remains available offline', self.features)
        self.assertIn('self.media_player.errorOccurred.connect(self.handle_media_error)', self.features)
        self.assertIn('def handle_media_error(self, _error, error_string):', self.features)
        self.assertIn('Missing files are handled gracefully.', self.features)

    def test_developer_and_faculty_layout_alignment_guards(self):
        developer_section = self.features[self.features.index('class DeveloperDialog(FeatureDialog):'):]
        self.assertIn('card.setMinimumHeight(255)', developer_section)
        self.assertIn('photo_status = QLabel("" if has_photo else', developer_section)
        self.assertIn('Registration No.: {registration_number}', developer_section)
        self.assertIn('faculty.setMinimumHeight(205)', developer_section)
        self.assertIn('faculty.setMaximumHeight(220)', developer_section)
        self.assertIn('faculty_layout.addStretch(1)', developer_section)
        self.assertIn('faculty_details.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)', developer_section)
        self.assertIn('faculty_department_label = QLabel(FACULTY_LABEL)', developer_section)
        self.assertIn('root.addWidget(faculty)', developer_section)
        self.assertNotIn('root.addWidget(faculty, 1)', developer_section)

    def test_question_bank_and_documents_share_canonical_source(self):
        self.assertIn('QUESTION_BANK', self.learning)
        self.assertIn('COMPETITIVE_QUESTIONS = QUESTION_BANK', self.learning)
        generator = (ROOT / 'tools' / 'generate_study_documents.py').read_text(encoding='utf-8')
        self.assertIn('generate_study_guide_pdf()', generator)
        self.assertIn('generate_quiz_pdf()', generator)
        self.assertIn('QUESTION_BANK', generator)
        self.assertIn("for package_name in ('reportlab', 'docx'):", self.spec)
        self.assertIn('collect_all(package_name)', self.spec)
        self.assertIn("('assets', 'assets')", self.spec)
        self.assertIn('Excludes: ".env,*.env,.env.*,*.env.*,*.pem,*.key,*.p12,*.pfx,*.sqlite,*.sqlite3,*.db,*.log,*.tmp,*.bak"', self.iss)
        self.assertIn('OutputDir=installer-output', self.iss)
        self.assertIn('QRYVANTA-Setup-{#MyAppVersion}-Offline-x64', self.iss)
        self.assertIn('Source: "docs\\*"; DestDir: "{app}\\docs"', self.iss)
        self.assertTrue((ROOT / 'compile_installer.bat').is_file())
        self.assertTrue((ROOT / 'GITHUB_PUBLISHING.md').is_file())
        self.assertIn('python tools/generate_study_documents.py', self.readme)


if __name__ == '__main__':
    unittest.main()
