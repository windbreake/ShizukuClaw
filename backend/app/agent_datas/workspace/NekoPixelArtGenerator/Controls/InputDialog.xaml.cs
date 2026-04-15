using System.ComponentModel;
using System.Windows;

namespace PixelArtGenerator.Controls
{
    public partial class InputDialog : Window, INotifyPropertyChanged
    {
        private string _inputText;
        private string _title;
        private string _message;

        public event PropertyChangedEventHandler PropertyChanged;

        public string InputText
        {
            get => _inputText;
            set
            {
                _inputText = value;
                OnPropertyChanged(nameof(InputText));
            }
        }

        public string Title
        {
            get => _title;
            set
            {
                _title = value;
                OnPropertyChanged(nameof(Title));
            }
        }

        public string Message
        {
            get => _message;
            set
            {
                _message = value;
                OnPropertyChanged(nameof(Message));
            }
        }

        public InputDialog(string title, string message, string defaultInput = "")
        {
            InitializeComponent();
            DataContext = this;

            Title = title;
            Message = message;
            InputText = defaultInput;
        }

        private void OKButton_Click(object sender, RoutedEventArgs e)
        {
            DialogResult = true;
        }

        private void CancelButton_Click(object sender, RoutedEventArgs e)
        {
            DialogResult = false;
        }

        protected virtual void OnPropertyChanged(string propertyName)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
        }
    }
}