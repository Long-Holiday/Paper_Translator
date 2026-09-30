#pragma once
#include <QDialog>
class QComboBox;
class QLineEdit;
class QSpinBox;
class SettingsDialog : public QDialog {
    Q_OBJECT
public:
    explicit SettingsDialog(QWidget *parent=nullptr);
private:
    void save();
    QComboBox *m_service;
    QLineEdit *m_model,*m_key,*m_url,*m_source,*m_target,*m_python;
    QSpinBox *m_threads;
};
